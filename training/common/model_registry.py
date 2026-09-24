"""Model artifact registry (brief section 32).

Model artifacts live at ``models/<capability>/<version>/`` with a
``metadata.yaml`` capturing dataset version, run id, git commit, taxonomy
version, and evaluation report reference. Never ``final_model``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from training.common.experiment import PROJECT_ROOT

MODELS_DIR = PROJECT_ROOT / "models"


def model_dir(capability: str, version: str) -> Path:
    return MODELS_DIR / capability / version


def register(capability: str, version: str, *, run_id: str, dataset_version: str, git_commit: str | None, taxonomy: str | None, extra: dict | None = None) -> Path:
    path = model_dir(capability, version)
    path.mkdir(parents=True, exist_ok=True)
    metadata = {
        "capability": capability,
        "version": version,
        "run_id": run_id,
        "dataset_version": dataset_version,
        "git_commit": git_commit,
        "taxonomy": taxonomy,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        **(extra or {}),
    }
    (path / "metadata.yaml").write_text(yaml.safe_dump(metadata, sort_keys=False), encoding="utf-8")
    return path


def versions(capability: str) -> list[str]:
    base = MODELS_DIR / capability
    if not base.exists():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir() and (p / "metadata.yaml").exists())
