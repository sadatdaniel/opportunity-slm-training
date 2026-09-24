#!/usr/bin/env bash
# Train the Supra classifier on a Colab GPU via google-colab-cli (brief 24/24A).
# Run from WSL Ubuntu after scripts/wsl_setup.sh and:
#   uv tool install google-colab-cli
#   colab auth          # interactive Google auth (browser)
#   cp ~/.oi_github_token ~/.colab_oi_github_token   # token available to the driver
set -euo pipefail

SESSION="${SESSION:-oi-trainer}"
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
tar -czf /tmp/oi_dataset.tar.gz -C "$REPO_DIR" datasets/classifier/v1

echo "== 3. upload =="
colab upload -s "$SESSION" "$TARBALL" /content/repo.tar.gz
colab upload -s "$SESSION" /tmp/oi_dataset.tar.gz /content/dataset.tar.gz

echo "== 4. extract + install locked deps =="
colab exec -s "$SESSION" <<'PY'
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

echo "== 5. train (resume from Drive checkpoint if present) =="
colab exec -s "$SESSION" <<'PY'
import glob, os, subprocess
checkpoints = sorted(glob.glob("/content/drive/MyDrive/opportunity_slm_runs/classifier_*/checkpoints/checkpoint-*"))
os.chdir("/content/repo")
if checkpoints:
    print("resuming from", checkpoints[-1])
    subprocess.run(["uv", "run", "python", "-m", "training.classifier.train",
                    "--resume-from-checkpoint", checkpoints[-1]], check=True)
else:
    subprocess.run(["uv", "run", "python", "-m", "training.classifier.train"], check=True)
PY

echo "== 6. download artifacts + manifests =="
colab exec -s "$SESSION" <<'PY'
import glob, subprocess, shutil
latest = sorted(glob.glob("/content/repo/runs/classifier_*/checkpoints/checkpoint-*"))
manifests = glob.glob("/content/repo/experiments/manifests/*.yaml")
shutil.make_archive("/content/oi_artifacts", "tar", root_dir="/content/repo", base_dir="models/classifier")
if latest:
    print("latest checkpoint:", latest[-1])
PY
colab download -s "$SESSION" /content/oi_artifacts.tar "$REPO_DIR/models/classifier_artifacts.tar" || true
colab download -s "$SESSION" /content/repo/experiments/manifests "$REPO_DIR/experiments/manifests" || true

echo "== done. Keep the session with: colab status -s $SESSION =="
echo "Stop later with: colab stop -s $SESSION (checkpoints must be on Drive first!)"
