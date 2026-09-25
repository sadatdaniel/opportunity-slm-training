import glob
import os
import subprocess

os.environ["CAPABILITY"] = "summarizer"
os.environ["TRAIN_MODULE"] = "training.summarizer.train"
os.chdir("/content/repo")

gpu = subprocess.run("nvidia-smi -L", shell=True, capture_output=True, text=True, check=False)
print("GPU:", gpu.stdout.strip() or gpu.stderr.strip(), flush=True)

result = subprocess.run(
    ["uv", "run", "python", "-m", "training.summarizer.train"],
    text=True,
)
print("train exit:", result.returncode, flush=True)
if result.returncode != 0:
    raise SystemExit(result.returncode)

subprocess.run(
    "cd /content/repo && tar cf /content/oi_artifacts.tar models/summarizer experiments/manifests",
    shell=True,
    check=True,
)
print("TRAINING_DONE", flush=True)
