"""Train the Supra-Classifier: a System-One decision model.

Architecture (brief section 4): Supra2-100M backbone + sequence-classification
head -> N logits -> softmax/calibration in application code. One forward pass,
no autoregressive generation, no ability to invent categories.

Device-portable: the same command runs on CPU (smoke), Colab GPU, or any GPU
host. Training is checkpointed and resumable (Trainer resume_from_checkpoint).

Usage::

    python -m training.classifier.train --smoke          # CPU pipeline proof
    python -m training.classifier.train                  # full run from config
    python -m training.classifier.train --resume         # continue latest run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
)

from datasets import Dataset
from training.common.datasets import label_maps, load_split, load_taxonomy_categories
from training.common.experiment import PROJECT_ROOT, Experiment
from training.common.model_registry import register
from training.common.drive_sync import DriveSyncCallback

CONFIG_PATH = PROJECT_ROOT / "training" / "classifier" / "config.yaml"


def build_dataset(split, tokenizer, label2id: dict[str, int], max_length: int, max_examples: int | None) -> Dataset:
    rows = split.examples if max_examples is None else split.examples[:max_examples]
    data = {
        "text": [r["input"] for r in rows],
        "label": [label2id[r["target"]] for r in rows],
    }
    dataset = Dataset.from_dict(data)

    def tokenize(batch):
        return tokenizer(batch["text"], truncation=True, max_length=max_length)

    return dataset.map(tokenize, batched=True, remove_columns=["text"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train the Supra classifier")
    parser.add_argument("--config", default=str(CONFIG_PATH))
    parser.add_argument("--smoke", action="store_true", help="tiny CPU run to prove the pipeline")
    parser.add_argument("--resume", action="store_true", help="resume from the latest checkpoint of the newest matching run")
    parser.add_argument(
        "--resume-from-checkpoint",
        dest="resume_from_checkpoint",
        default=None,
        help="exact checkpoint dir (brief 24A); run identity continues from that run",
    )
    args = parser.parse_args(argv)

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    smoke = config["smoke"] if args.smoke else None
    if smoke:
        config = {**config, "epochs": smoke["epochs"], "batch_size": smoke["batch_size"]}

    resume_path = args.resume_from_checkpoint
    if resume_path:
        # continue the SAME run identity: runs/<run_id>/checkpoints/checkpoint-N
        run_id = Path(resume_path).resolve().parents[1].name
        config = {**config, "run_id": run_id}
    elif args.resume:
        existing = sorted((PROJECT_ROOT / "runs").glob("classifier_*/checkpoints/checkpoint-*"))
        if existing:
            resume_path = str(existing[-1])
            config = {**config, "run_id": existing[-1].resolve().parents[1].name}

    exp = Experiment("classifier", config, Path(args.config))
    exp.log(f"device={exp.device} dataset={config['dataset_version']}")
    if resume_path:
        exp.log(f"resuming from {resume_path}")

    import torch  # noqa: F401 - imported after Experiment so errors are explicit

    tokenizer = AutoTokenizer.from_pretrained(config["model"], revision=config.get("model_revision", "main"))
    categories = load_taxonomy_categories()
    label2id, id2label = label_maps(categories)

    train_split = load_split("classifier", config["dataset_version"], "train")
    val_split = load_split("classifier", config["dataset_version"], "validation")
    max_examples = smoke["max_examples"] if smoke else None
    train_ds = build_dataset(train_split, tokenizer, label2id, config["max_seq_length"], max_examples)
    val_ds = build_dataset(val_split, tokenizer, label2id, config["max_seq_length"], max_examples)
    exp.log(f"train={len(train_ds)} validation={len(val_ds)} labels={len(categories)}")

    model = AutoModelForSequenceClassification.from_pretrained(
        config["model"],
        revision=config.get("model_revision", "main"),
        num_labels=len(categories),
        id2label=id2label,
        label2id=label2id,
    )

    use_bf16 = config.get("precision") == "bf16" and exp.device == "cuda"
    # transformers 5 dropped warmup_ratio; express the configured ratio in steps
    steps_per_epoch = max(1, len(train_ds) // (config["batch_size"] * config.get("gradient_accumulation", 1)))
    warmup_steps = int(steps_per_epoch * config["epochs"] * config.get("warmup_ratio", 0.06))
    training_args = TrainingArguments(
        output_dir=str(exp.output_dir / "checkpoints"),
        num_train_epochs=config["epochs"],
        per_device_train_batch_size=config["batch_size"],
        per_device_eval_batch_size=config["batch_size"],
        gradient_accumulation_steps=config.get("gradient_accumulation", 1),
        learning_rate=config["learning_rate"],
        warmup_steps=warmup_steps,
        weight_decay=config.get("weight_decay", 0.0),
        bf16=use_bf16,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        logging_steps=10,
        report_to=[],
        seed=config.get("seed", 42),
    )

    callbacks = []
    drive_dir = os.environ.get("DRIVE_SYNC_DIR")
    if drive_dir:
        callbacks.append(DriveSyncCallback(str(training_args.output_dir), drive_dir, f"classifier_{exp.run_id}"))

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        processing_class=tokenizer,
        callbacks=callbacks,
    )

    trainer.train(resume_from_checkpoint=resume_path)
    metrics = trainer.evaluate()
    exp.log(f"validation: {metrics}")

    output_version = smoke["output_version"] if smoke else config["output_version"]
    save_dir = PROJECT_ROOT / "models" / "classifier" / output_version
    trainer.save_model(str(save_dir))
    tokenizer.save_pretrained(str(save_dir))
    register(
        "classifier",
        output_version,
        run_id=exp.run_id,
        dataset_version=config["dataset_version"],
        git_commit=exp.manifest()["git_commit"] if False else None,
        taxonomy=config["taxonomy"],
        extra={"validation_metrics": {k: v for k, v in metrics.items()}},
    )
    exp.manifest(metrics={"validation": metrics}, checkpoint=str(exp.output_dir / "checkpoints"))
    exp.log(f"model saved to {save_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
