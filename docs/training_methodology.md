# Training Methodology

Living document — updated as decisions are made, not only after experiments
(brief 24A). Formal learning explanations live in `docs/learning_notes.md`.

## Reproducibility contract

Every run is reconstructable from: Git commit + `uv.lock` + frozen dataset
version/hash + model revision + run config + latest valid checkpoint. The
run manifest (`experiments/manifests/<run_id>.yaml`) records all of these
plus hardware, seed, hyperparameters, and metrics.

## Environments vs checkpoints

- Docker (`Dockerfile.dev`/compose, prefix `opportunity_slm_`) provides the
  reproducible environment. The container filesystem is disposable — never
  authoritative storage for training progress.
- Checkpoints provide run continuation. HF `Trainer` checkpoints under
  `runs/<run_id>/checkpoints/checkpoint-N/` preserve weights, optimizer,
  scheduler, RNG, and trainer state (PyTorch-native, no custom format).
- Resume: `python -m training.classifier.train --resume-from-checkpoint
  runs/<run_id>/checkpoints/checkpoint-N` continues the same run identity
  (run_id is derived from the checkpoint path, never re-issued).

## Classifier (Supra-Classifier, System-One Choice)

- **Objective**: categorical classification over taxonomy_v1's 12 categories.
- **Backbone**: `SupraLabs/Supra2-100M-Instruct` with a
  sequence-classification head (`AutoModelForSequenceClassification`) —
  one forward pass, non-autoregressive, cannot invent categories.
- **Dataset**: `classifier_dataset_v1` built by `project.build_dataset` from
  teacher pilot + full annotations; gold/silver tiers (quarantine excluded);
  duplicate-group-aware splits; unseen-source holdout; frozen test set.
- **Loss**: cross-entropy over the 12 logits (head training + light backbone
  tuning; LoRA variant to be compared per brief 3).
- **Sequence length**: 512 (tokenizer stats: p90 input ≈ 890 tokens full;
  classification truncates harder — front-loaded eligibility text survives).
- **Optimization**: AdamW, lr 2e-5, linear schedule, warmup 6%, wd 0.01,
  batch 16 (grad accumulation 1), 3 epochs, bf16 on CUDA / fp32 CPU, seed 42.
- **Checkpoint frequency**: per epoch (+ periodic mid-epoch for long runs);
  best-by-validation-loss is restored at end.
- **Model selection**: best validation loss; then calibration fit on
  validation; test set touched exactly once per release.
- **Calibration**: temperature scaling fit on validation logits; raw and
  calibrated probabilities both preserved.
- **Resume**: `--resume` (latest) or `--resume-from-checkpoint <dir>`.
- **Hardware**: free Colab GPU (record actual accelerator in manifest);
  CPU smoke mode (`--smoke`) proves the pipeline on 32 examples.

## Summarizer (Supra-Summarizer)

- **Objective**: ≤150-word high-signal summary in the fixed section format
  (MANDATORY/RESTRICTIONS/IMPORTANT/PREFERRED/SUMMARY), completion-only loss.
- **Backbone**: same base model, trained with TRL SFT (prompt/completion
  format → loss on completion only).
- **Dataset**: summarizer dataset versions (pilot 300 → scale by measured
  gains, brief step 9); same split/leakage rules as the classifier.
- **Sequence length**: 1536 (tokenizer stats: 100% of prompt+target fit).
- **Variants to compare**: full fine-tuning vs LoRA (both first-class).
- Everything else (seed, resume, manifests) identical to the classifier.

## Noul (binary System-One verification)

- v0: no trained Noul model — the SystemOne engine scores criteria with the
  backbone LM (prototype protocol, `config/noul_families.yaml`).
- Training data plan: derived-label prototype set (`project.build_noul_set`)
  for protocol mechanics; real training data comes from the reviewed
  extraction pass with positive/negative/negated/qualified/ambiguous cases
  (brief 4A), then a two-way head or criterion-scoring model.
- Thresholds: chosen from held-out calibration data via
  `training.noul.evaluate` threshold tables, never assumed 0.5.

## Colab workflow (durable checkpoints)

See `docs/colab_workflow.md`. Pattern: train on fast local disk → complete
checkpoint → validate → sync periodically to Drive; fresh runtime resumes
from the latest valid durable checkpoint and logs to the same manifest.
Test with a deliberately interrupted smoke run before the real experiment.
