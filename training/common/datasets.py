"""Dataset loading for training/evaluation.

Datasets live at ``datasets/<capability>/<version>/{split}.jsonl`` produced by
``project.build_dataset`` (leakage-aware, frozen, hashed). This module only
reads them and formats them per capability.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import yaml

from training.common.experiment import PROJECT_ROOT

DATASETS_DIR = PROJECT_ROOT / "datasets"


@dataclass
class Split:
    name: str
    examples: list[dict]

    def __len__(self) -> int:
        return len(self.examples)


def load_split(capability: str, version: str, split: str) -> Split:
    path = DATASETS_DIR / capability / version / f"{split}.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"missing dataset split: {path} — run project.build_dataset first")
    examples = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return Split(name=split, examples=examples)


def load_taxonomy_categories() -> list[str]:
    config = yaml.safe_load((PROJECT_ROOT / "config" / "taxonomy_v1.yaml").read_text(encoding="utf-8"))
    return list(config["categories"])


def label_maps(categories: list[str]) -> tuple[dict[str, int], dict[int, str]]:
    id2label = dict(enumerate(categories))
    label2id = {label: i for i, label in id2label.items()}
    return label2id, id2label
