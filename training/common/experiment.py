"""Experiment plumbing: device detection, seeding, manifests, run ids.

Every training run produces a manifest (brief sections 25, 36) capturing
model, revisions, dataset version + hashes, taxonomy, git commit, prompt
version, hyperparameters, seed, hardware, timing, metrics, and checkpoint
path — so any run can be reconstructed and audited.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import random
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = PROJECT_ROOT / "experiments" / "manifests"


def detect_device() -> str:
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def detect_hardware(device: str) -> dict:
    info = {
        "device": device,
        "platform": platform.platform(),
        "python": platform.python_version(),
    }
    try:
        import torch
        import transformers

        info["torch"] = str(torch.__version__)
        info["transformers"] = str(transformers.__version__)
        try:
            import trl
            import peft

            info["trl"] = trl.__version__
            info["peft"] = peft.__version__
        except ImportError:
            pass
        if device == "cuda":
            info["gpu"] = torch.cuda.get_device_name(0)
            info["vram_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1)
            info["cuda"] = torch.version.cuda
    except ImportError:
        pass
    return info


def set_seed(seed: int) -> None:
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


def git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dataset_hashes(dataset_dir: Path) -> dict:
    return {
        path.name: file_sha256(path)
        for path in sorted(dataset_dir.glob("*.jsonl"))
    }


class Experiment:
    """Context object for one training/evaluation run."""

    def __init__(self, capability: str, config: dict, config_path: Path):
        self.capability = capability
        self.config = config
        self.config_path = config_path
        self.run_id = config.get("run_id") or f"{capability}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self.seed = int(config.get("seed", 42))
        self.device = detect_device()
        self.started = time.time()
        self.output_dir = PROJECT_ROOT / "runs" / self.run_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        set_seed(self.seed)

    def hardware(self) -> dict:
        return detect_hardware(self.device)

    def manifest(self, metrics: dict | None = None, checkpoint: str | None = None) -> Path:
        dataset_dir = PROJECT_ROOT / "datasets" / self.capability / self.config.get("dataset_version", "")
        payload = {
            "run_id": self.run_id,
            "capability": self.capability,
            "git_commit": git_commit(),
            "model": self.config.get("model"),
            "model_revision": self.config.get("model_revision", "main"),
            "dataset_version": self.config.get("dataset_version"),
            "dataset_sha256": dataset_hashes(dataset_dir) if dataset_dir.exists() else None,
            "taxonomy": self.config.get("taxonomy"),
            "prompt_version": self.config.get("prompt_version"),
            "seed": self.seed,
            "hyperparameters": {
                k: v for k, v in self.config.items()
                if k in ("epochs", "learning_rate", "batch_size", "gradient_accumulation",
                         "max_seq_length", "precision", "lora", "lora_r", "lora_alpha",
                         "optimizer", "scheduler", "warmup_ratio", "weight_decay")
            },
            "hardware": self.hardware(),
            "elapsed_seconds": round(time.time() - self.started, 1),
            "checkpoint_path": checkpoint,
            "config_snapshot": self.config,
            "metrics": metrics,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
        path = MANIFEST_DIR / f"{self.run_id}.yaml"
        path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return path

    def log(self, message: str) -> None:
        line = f"[{self.run_id}] {message}"
        print(line, flush=True)
        with (self.output_dir / "log.txt").open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
