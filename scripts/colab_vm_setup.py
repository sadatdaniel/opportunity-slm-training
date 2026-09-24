#!/usr/bin/env python3
"""On-VM setup: extract repo + dataset, install locked training deps."""
import subprocess

cmds = [
    "cd /content && rm -rf repo && mkdir -p repo && tar xzf repo.tar.gz -C repo",
    "cd /content && mkdir -p repo/datasets/classifier && tar xzf dataset.tar.gz -C repo/",
    "cd /content/repo && pip -q install uv && uv sync --group training",
]
for c in cmds:
    print("$", c, flush=True)
    subprocess.run(c, shell=True, check=True)
print("SETUP_OK", flush=True)
