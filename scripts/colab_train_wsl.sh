#!/usr/bin/env bash
# Train the Supra classifier on a Colab GPU via google-colab-cli (brief 24/24A).
# Run from WSL Ubuntu after scripts/wsl_setup.sh and:
#   uv tool install google-colab-cli
#   colab auth          # interactive Google auth (browser)
#   cp ~/.oi_github_token ~/.colab_oi_github_token   # token available to the driver
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"
SESSION="${SESSION:-oi-trainer}"
# Capability is argument 1 (env vars do NOT propagate Windows->WSL without
# WSLENV; arg-passing is robust). classifier | summarizer.
CAPABILITY="${1:-classifier}"
TRAIN_MODULE="training.${CAPABILITY}.train"
GPU="${GPU:-T4}"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "== 1. allocate GPU runtime =="
colab new -s "$SESSION" --gpu "$GPU" || colab status -s "$SESSION"

echo "== 2. package repo (code + frozen dataset; token never leaves this machine) =="
STAMP="$(date +%Y%m%d_%H%M%S)"
TARBALL="/tmp/oi_repo_${STAMP}.tar.gz"
git -C "$REPO_DIR" archive --format=tar.gz -o "$TARBALL" HEAD
git -C "$REPO_DIR" archive --format=tar.gz -o /tmp/oi_dataset.tar.gz HEAD datasets/classifier config training project collectors sources 2>/dev/null || true
# datasets are git-ignored: tar them separately from the working tree
tar -czf /tmp/oi_dataset.tar.gz -C "$REPO_DIR" datasets/classifier

echo "== 3. upload =="
colab upload -s "$SESSION" "$TARBALL" /content/repo.tar.gz
colab upload -s "$SESSION" /tmp/oi_dataset.tar.gz /content/dataset.tar.gz

echo "== 4. extract + install locked deps =="
colab exec -s "$SESSION" --timeout 1800 <<'PY'
import subprocess
cmds = [
    "cd /content && mkdir -p repo && tar xzf repo.tar.gz -C repo",
    "cd /content && mkdir -p repo/datasets/classifier && tar xzf dataset.tar.gz -C repo/",
    "cd /content/repo && pip -q install uv && uv sync --group training",
]
for c in cmds:
    print("$", c)
    subprocess.run(c, shell=True, check=True)
PY

echo "== 4b. mount Drive for durable checkpoints (non-fatal) =="
timeout 120 colab drivemount -s "$SESSION" /content/drive 2>&1 | tail -1 || echo "(drive mount failed - continuing without durable sync)"

echo "== 5. train (resume from Drive checkpoint if present) =="
# NOTE: a lost WebSocket mid-training is retryable — the kernel may have
# kept running. Before relaunching a fresh session, reconnect and probe
# /content for artifacts (scripts/colab_vm_probe.py).
# capability-specific driver file: the VM does not inherit local env vars,
# so CAPABILITY/TRAIN_MODULE are set INSIDE the driver (hardcoded per file)
DRIVER="$REPO_DIR/scripts/colab_vm_train_${CAPABILITY}.py"
[ -f "$DRIVER" ] || DRIVER="$REPO_DIR/scripts/colab_vm_train.py"
colab exec -s "$SESSION" --timeout 3600 -f "$DRIVER" 2>&1 | tail -6

echo "== 6. download artifacts + manifests =="
colab exec -s "$SESSION" <<'PY'
import glob, subprocess, shutil
latest = sorted(glob.glob(f"/content/repo/runs/{os.environ.get('CAPABILITY', 'classifier')}_*/checkpoints/checkpoint-*"))
manifests = glob.glob("/content/repo/experiments/manifests/*.yaml")
shutil.make_archive("/content/oi_artifacts", "tar", root_dir="/content/repo", base_dir=f"models/{os.environ.get('CAPABILITY', 'classifier')}")
shutil.make_archive("/content/oi_manifests", "tar", root_dir="/content/repo", base_dir="experiments/manifests")
if latest:
    print("latest checkpoint:", latest[-1])
PY
colab download -s "$SESSION" /content/oi_artifacts.tar "$REPO_DIR/models/classifier_artifacts.tar" || true
colab download -s "$SESSION" /content/repo/experiments/manifests "$REPO_DIR/experiments/manifests" || true

echo "== 7. release the runtime (quota is billed on connection time) =="
colab stop -s "$SESSION"

echo "== done =="
