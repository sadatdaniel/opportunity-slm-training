#!/usr/bin/env python3
"""On-VM training driver: run the full classifier experiment, then report."""
import glob
import json
import os
import subprocess

os.chdir("/content/repo")

# 1. verify GPU and record environment
gpu = subprocess.run("nvidia-smi -L", shell=True, capture_output=True, text=True)
print("GPU:", gpu.stdout.strip() or gpu.stderr.strip(), flush=True)

# 2. train (full config: 3 epochs, batch 16, bf16 auto-off -> fp32 on T4? bf16 supported on T4? T4 is sm75: bf16 unsupported, script auto-disables and trains fp32)
result = subprocess.run(
    ["uv", "run", "python", "-m", "training.classifier.train"],
    capture_output=False,
    text=True,
)
print("train exit:", result.returncode, flush=True)
if result.returncode != 0:
    raise SystemExit(result.returncode)

# 3. package artifacts + manifests for download
subprocess.run("cd /content/repo && tar cf /content/oi_artifacts.tar models/classifier experiments/manifests", shell=True, check=True)
manifests = sorted(glob.glob("/content/repo/experiments/manifests/*.yaml"))
print("MANIFESTS:", json.dumps([os.path.basename(m) for m in manifests]), flush=True)
print("TRAINING_DONE", flush=True)
