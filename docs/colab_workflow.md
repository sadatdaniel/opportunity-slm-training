# Colab Training Workflow

Training runs on free Google Colab GPUs; the local Windows machine handles
development, preprocessing, annotation, review, tests, and CPU smoke tests.
Training logic lives in ordinary Python modules (`training/...`) — Colab
executes those scripts, it does not own them (brief 24).

## Two ways to run

1. **Browser notebook (works today, no WSL needed)** — `colab/colab_train.ipynb`:
   clone the private repo, install the locked deps, run the same module
   commands. Good for the first experiments.
2. **google-colab-cli from WSL2 (planned)** — the CLI does not support native
   Windows and WSL currently only has the docker-desktop distro; installing
   Ubuntu (`wsl --install Ubuntu`) needs user action and must not block
   anything else.

## Resume contract (brief 24A)

A fresh runtime reconstructs the run from: Git commit + `uv.lock` + frozen
dataset (by version/hash from the run manifest) + model revision + config +
latest valid checkpoint:

1. provision runtime, mount Drive as `DRIVE_ROOT`
2. `git clone` the repo at the manifest's `git_commit`
3. `uv pip install -r requirements-colab.txt` (or `uv sync --group training`)
4. fetch the frozen dataset version (Drive cache or rebuild + hash-check)
5. locate the latest valid checkpoint on Drive (`.complete` marker present)
6. `python -m training.classifier.train --resume-from-checkpoint <path>`
7. the run manifest keeps the same `run_id`; metrics append, not reset
8. at end (and periodically), sync `runs/<run_id>/` back to Drive

Checkpoint durability: HF checkpoints save atomically; the sync step writes a
`.complete` marker only after a checkpoint directory is fully copied, so a
runtime death mid-sync never leaves a partial checkpoint looking valid.

## Test before trusting

Before the real run: deliberately interrupt a CPU/GPU smoke run mid-training,
then resume from the Drive-synced checkpoint and verify (a) the run id
continues, (b) global steps continue, (c) final metrics match a non-interrupted
control. This is the acceptance test for the resume workflow (brief 24A).
