"""One-click Colab cell: Qwen3-0.6B classifier — train + evaluate + Drive sync.

Paste this single cell into the Colab notebook (T4 runtime, repo already
cloned at /content/opportunity-slm-training, Drive mounted) and run.
Upload classifier_dataset_v4.tar.gz via the Files pane first if the
datasets/classifier/v4 directory is not already extracted.

Stages print [1/4]..[4/4]; the cell stops loudly if training fails.
"""

import os, glob, shutil

DRIVE = "/content/drive/MyDrive/opportunity_slm_runs"

# 0. latest code
os.system("git checkout -q -- . && git pull -q origin")

# 1. dataset v4 (from uploaded tarball or previous extraction)
if not os.path.isdir("datasets/classifier/v4"):
    assert os.path.isfile("/content/classifier_dataset_v4.tar.gz"), \
        "upload classifier_dataset_v4.tar.gz via the Files pane first"
    os.makedirs("datasets/classifier", exist_ok=True)
    os.system("tar xzf /content/classifier_dataset_v4.tar.gz -C datasets/classifier")
print("[1/4] dataset v4 ready:",
      os.path.isfile("datasets/classifier/v4/train.jsonl"), flush=True)

# 2. train — Qwen3-0.6B, fp16, dataset v4 (~40-50 min on T4)
os.environ["DRIVE_SYNC_DIR"] = DRIVE
print("[2/4] training...", flush=True)
r = os.system("uv run python -m training.classifier.train "
              "--config training/classifier/config_qwen06.yaml")
print("train exit:", r, flush=True)
assert r == 0, "training failed — paste the output above"

# 3. evaluate on the frozen test split (241 records, never trained on)
print("[3/4] evaluating...", flush=True)
r = os.system("uv run python -m training.classifier.evaluate "
              "--model models/classifier/v0.3.0-qwen06 --dataset-version v4")
print("eval exit:", r, flush=True)

# 4. sync everything to Drive (model + manifest + eval report)
for f in glob.glob("models/classifier/v0.3.0-qwen06/*"):
    shutil.copy2(f, DRIVE + "/qwen06_model_" + os.path.basename(f))
for m in (glob.glob("experiments/manifests/*.yaml")
          + glob.glob("reports/classifier_eval_*.json")):
    shutil.copy2(m, DRIVE + "/" + os.path.basename(m))
print("[4/4] SYNCED TO DRIVE — model + manifest + eval report", flush=True)
