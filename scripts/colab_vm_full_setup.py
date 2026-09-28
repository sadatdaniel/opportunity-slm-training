"""One-shot VM setup: Drive + clone + deps + datasets."""
import os
import shutil
import subprocess

# 1. Drive
from google.colab import drive
drive.mount("/content/drive")
os.environ["DRIVE_SYNC_DIR"] = "/content/drive/MyDrive/opportunity_slm_runs/drive_sync"
print("[1/4] Drive mounted", flush=True)

# 2. clone
if not os.path.isdir("/content/opportunity-slm-training"):
    subprocess.run("git clone -q https://github.com/sadatdaniel/opportunity-slm-training.git /content/opportunity-slm-training", shell=True, check=True)
os.chdir("/content/opportunity-slm-training")
subprocess.run("git checkout -q -- . && git pull -q origin", shell=True, check=True)
print("[2/4] repo pulled", flush=True)

# 3. deps
subprocess.run("pip -q install uv", shell=True, check=True)
subprocess.run("uv sync --group training", shell=True, check=True, capture_output=True)
print("[3/4] deps installed", flush=True)

# 4. datasets from Drive
ROOT = "/content/drive/MyDrive/opportunity_slm_runs"
for name, subdir in [("classifier_dataset_v4.tar.gz", "classifier"), ("summarizer_dataset_v4.tar.gz", "summarizer")]:
    src = f"{ROOT}/datasets/{name}"
    if os.path.isfile(src):
        os.makedirs(f"datasets/{subdir}", exist_ok=True)
        subprocess.run(f"tar xzf {src} -C datasets/{subdir}", shell=True, check=True)
        print(f"  extracted {name}", flush=True)

for cap in ("classifier", "summarizer"):
    print(f"  {cap} v4:", os.path.isfile(f"datasets/{cap}/v4/train.jsonl"), flush=True)

print("[4/4] SETUP COMPLETE", flush=True)
