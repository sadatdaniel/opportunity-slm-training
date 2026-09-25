"""Train the Supra-Summarizer: supervised fine-tuning for high-signal summaries.

TRL SFT with prompt/completion pairs — loss is computed on the completion
only (the model never learns to write opportunity text). Both full
fine-tuning and LoRA are first-class variants (brief section 3).

Device-portable (CPU smoke / Colab GPU / any GPU), checkpointed and
resumable with `--resume-from-checkpoint` (run identity continues).

Usage::

    python -m training.summarizer.train --smoke
    python -m training.summarizer.train
    python -m training.summarizer.train --variant lora
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml
from datasets import Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer

from training.common.datasets import load_split
from training.common.experiment import Experiment, PROJECT_ROOT
from training.common.model_registry import register
from training.summarizer.prompt import render_prompt

CONFIG_PATH = PROJECT_ROOT / "training" / "summarizer" / "config.yaml"

CHAT_TEMPLATE = (
    "Summarize the following opportunity posting as high-signal intelligence. "
    "Use sections DEADLINE / MANDATORY / RESTRICTIONS / TARGET GROUP / "
    "FUNDING / BENEFITS / APPLICATION / OTHER IMPORTANT CONDITIONS / SUMMARY "
    "(omit empty sections), at most 150 words, and never invent information.\n\n"
    "OPPORTUNITY:\n{input}"
)


def build_dataset(split, tokenizer, max_examples: int | None) -> Dataset:
    """Raw prompt/completion TEXT dataset: TRL performs its own tokenization,
    EOS handling, and completion-only masking — pre-tokenizing concatenated
    text destroyed the mask and produced a full-sequence LM (root cause of
    the v0.1.0 negative result, see experiments/summarizer_20260925_073307.md).
    Prompts are rendered through the model's native chat template with a
    one-shot exemplar (train and evaluate share the builder)."""
    rows = split.examples if max_examples is None else split.examples[:max_examples]
    return Dataset.from_dict({
        "prompt": [render_prompt(tokenizer, r["input"]) for r in rows],
        "completion": [r["target"] for r in rows],
    })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train the Supra summarizer")
    parser.add_argument("--config", default=str(CONFIG_PATH))
    parser.add_argument("--variant", choices=["full", "lora"], default=None, help="override config variant")
    parser.add_argument("--smoke", action="store_true", help="tiny CPU run to prove the pipeline")
    parser.add_argument("--resume", action="store_true", help="resume from the newest matching run")
    parser.add_argument("--resume-from-checkpoint", dest="resume_from_checkpoint", default=None)
    args = parser.parse_args(argv)

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    smoke = config["smoke"] if args.smoke else None
    if smoke:
        config = {**config, "epochs": smoke["epochs"], "batch_size": smoke["batch_size"]}
    variant = args.variant or config.get("variant", "full")

    resume_path = args.resume_from_checkpoint
    if resume_path:
        config = {**config, "run_id": Path(resume_path).resolve().parents[1].name}
    elif args.resume:
        existing = sorted((PROJECT_ROOT / "runs").glob(f"summarizer_*/checkpoints/checkpoint-*"))
        if existing:
            resume_path = str(existing[-1])
            config = {**config, "run_id": existing[-1].resolve().parents[1].name}

    exp = Experiment("summarizer", config, Path(args.config))
    exp.log(f"device={exp.device} variant={variant} dataset={config['dataset_version']}")

    import torch  # noqa: F401
    from peft import LoraConfig
    from trl import SFTConfig, SFTTrainer

    tokenizer = AutoTokenizer.from_pretrained(config["model"], revision=config.get("model_revision", "main"))
    train_split = load_split("summarizer", config["dataset_version"], "train")
    val_split = load_split("summarizer", config["dataset_version"], "validation")
    max_examples = smoke["max_examples"] if smoke else None
    train_ds = build_dataset(train_split, tokenizer, max_examples)
    val_ds = build_dataset(val_split, tokenizer, max_examples)
    exp.log(f"train={len(train_ds)} validation={len(val_ds)}")

    model = AutoModelForCausalLM.from_pretrained(
        config["model"], revision=config.get("model_revision", "main")
    )
    peft_config = None
    if variant == "lora":
        lora_cfg = config.get("lora", {})
        peft_config = LoraConfig(
            r=lora_cfg.get("r", 16),
            lora_alpha=lora_cfg.get("alpha", 32),
            lora_dropout=lora_cfg.get("dropout", 0.05),
            target_modules=lora_cfg.get("target_modules"),
            task_type="CAUSAL_LM",
        )

    use_bf16 = config.get("precision") == "bf16" and exp.device == "cuda"
    steps_per_epoch = max(1, len(train_ds) // (config["batch_size"] * config.get("gradient_accumulation", 1)))
    warmup_steps = int(steps_per_epoch * config["epochs"] * config.get("warmup_ratio", 0.03))
    lr = config["lora_learning_rate"] if variant == "lora" else config["learning_rate"]

    training_args = SFTConfig(
        output_dir=str(exp.output_dir / "checkpoints"),
        num_train_epochs=config["epochs"],
        per_device_train_batch_size=config["batch_size"],
        per_device_eval_batch_size=config["batch_size"],
        gradient_accumulation_steps=config.get("gradient_accumulation", 1),
        learning_rate=lr,
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
        max_length=config["max_seq_length"],
        packing=False,
        completion_only_loss=True,  # loss on the summary only
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        processing_class=tokenizer,
        peft_config=peft_config,
    )

    trainer.train(resume_from_checkpoint=resume_path)
    metrics = trainer.evaluate()
    exp.log(f"validation: {metrics}")

    output_version = smoke["output_version"] if smoke else config["output_version"]
    save_dir = PROJECT_ROOT / "models" / "summarizer" / output_version
    trainer.save_model(str(save_dir))
    tokenizer.save_pretrained(str(save_dir))
    register(
        "summarizer",
        output_version,
        run_id=exp.run_id,
        dataset_version=config["dataset_version"],
        git_commit=None,
        taxonomy=None,
        extra={"variant": variant, "validation_metrics": metrics},
    )
    exp.manifest(metrics={"validation": metrics, "variant": variant}, checkpoint=str(exp.output_dir / "checkpoints"))
    exp.log(f"model saved to {save_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
