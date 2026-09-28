"""Setup + train classifier, no Drive needed."""
import os, subprocess

# 1. extract
subprocess.run("cd /content && rm -rf repo && mkdir repo && tar xzf repo.tar.gz -C repo", shell=True, check=True)
subprocess.run("cd /content/repo && mkdir -p datasets/classifier datasets/summarizer && tar xzf /content/datasets.tar.gz -C datasets/classifier --strip-components=2 classifier/v4 2>/dev/null; tar xzf /content/datasets.tar.gz -C datasets/summarizer --strip-components=2 summarizer/v4 2>/dev/null; true", shell=True)
os.chdir("/content/repo")

# fix dataset structure (tar strip can be finicky — rebuild if needed)
for cap in ("classifier", "summarizer"):
    if not os.path.isfile(f"datasets/{cap}/v4/train.jsonl"):
        subprocess.run(f"mkdir -p datasets/{cap} && tar xzf /content/datasets.tar.gz -C datasets/{cap} --strip-components=1 {cap}/v4", shell=True)
    print(f"  {cap} v4:", os.path.isfile(f"datasets/{cap}/v4/train.jsonl"), flush=True)

# 2. deps
subprocess.run("pip -q install uv", shell=True, check=True)
subprocess.run("uv sync --group training", shell=True, check=True, capture_output=True)
print("[SETUP] deps ready", flush=True)

# 3. train classifier
r = subprocess.run(["uv", "run", "python", "-m", "training.classifier.train",
                    "--config", "training/classifier/config_qwen06.yaml"], text=True)
print(f"classifier train exit: {r.returncode}", flush=True)

# 4. evaluate
if r.returncode == 0:
    r2 = subprocess.run(["uv", "run", "python", "-m", "training.classifier.evaluate",
                         "--model", "models/classifier/v0.3.0-qwen06",
                         "--dataset-version", "v4"], text=True)
    print(f"eval exit: {r2.returncode}", flush=True)

    # 5. package artifacts for download
    subprocess.run("cd /content/repo && tar cf /content/classifier_artifacts.tar models/classifier/v0.3.0-qwen06 experiments/manifests reports/classifier_eval_*.json", shell=True)
    print("ARTIFACTS_READY at /content/classifier_artifacts.tar", flush=True)
else:
    print("TRAINING FAILED — check output above", flush=True)
