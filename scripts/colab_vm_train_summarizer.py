import glob
import os
import subprocess

os.environ["CAPABILITY"] = "summarizer"
os.environ["TRAIN_MODULE"] = "training.summarizer.train"
os.chdir("/content/repo")

gpu = subprocess.run("nvidia-smi -L", shell=True, capture_output=True, text=True, check=False)
print("GPU:", gpu.stdout.strip() or gpu.stderr.strip(), flush=True)

result = subprocess.run(
    ["uv", "run", "python", "-m", "training.summarizer.train"] + RESUME_ARGS,
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

# durable sync (brief 24A): Drive survives VM recycling; .complete markers
# make partial copies detectable
drive_root = "/content/drive/MyDrive/opportunity_slm_runs"
if os.path.isdir("/content/drive/MyDrive"):
    import glob as _g
    import shutil as _sh
    _sh.makedirs(f"{drive_root}/summarizer", exist_ok=True)
    for ckpt in _g.glob("/content/repo/runs/summarizer_*/checkpoints/checkpoint-*"):
        dst = f"{drive_root}/summarizer/{_g.basename(os.path.dirname(ckpt))}/{_g.basename(ckpt)}"
        _sh.copytree(ckpt, dst, dirs_exist_ok=True)
        open(f"{dst}/.complete", "w").close()
    for artifact in _g.glob("/content/repo/models/summarizer/*"):
        dst = f"{drive_root}/summarizer_model/{_g.basename(artifact)}"
        _sh.copy2(artifact, dst)
    for man in _g.glob("/content/repo/experiments/manifests/*.yaml"):
        _sh.copy2(man, f"{drive_root}/manifests/")
    print("DRIVE_SYNC_OK", flush=True)
else:
    print("DRIVE_NOT_MOUNTED - artifacts only on VM", flush=True)

