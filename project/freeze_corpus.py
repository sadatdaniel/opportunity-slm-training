"""Freeze a corpus version as an immutable, reproducible artifact (v2 brief, 39A step 1).

Records the canonical records' hash, source distribution, duplicate-group
state, normalization parameters, and the Git commit into
``data/manifests/corpus_<version>.yaml``. The manifest is committed; the
records file itself stays private and is identified by its hash.

Usage::

    python -m project.freeze_corpus                    # freeze v1 (refuses to overwrite)
    python -m project.freeze_corpus --version v2       # freeze a later corpus
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEDUPED_PATH = PROJECT_ROOT / "data" / "normalized" / "deduped.jsonl"
GROUPS_PATH = PROJECT_ROOT / "data" / "manifests" / "duplicate_groups.json"
MANIFEST_DIR = PROJECT_ROOT / "data" / "manifests"

NORMALIZATION_PARAMS = {"min_words": 40, "language_filter": "en", "noise_patterns_version": 1}


def git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def freeze(version: str) -> Path:
    if not DEDUPED_PATH.exists():
        print(f"missing {DEDUPED_PATH} - run project.normalize && project.dedupe first")
        raise SystemExit(1)

    records = [
        json.loads(line)
        for line in DEDUPED_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    by_source = Counter(r["source_id"] for r in records)

    groups = json.loads(GROUPS_PATH.read_text(encoding="utf-8")) if GROUPS_PATH.exists() else []
    multi_groups = [g for g in groups if g["size"] > 1]

    data_hash = hashlib.sha256(DEDUPED_PATH.read_bytes()).hexdigest()
    manifest = {
        "corpus": f"corpus_{version}",
        "created_at": datetime.now(UTC).isoformat(),
        "git_commit": git_commit(),
        "records_file": str(DEDUPED_PATH.relative_to(PROJECT_ROOT)),
        "records_sha256": data_hash,
        "record_count": len(records),
        "source_distribution": dict(by_source.most_common()),
        "productive_sources": len(by_source),
        "duplicate_groups_total": len(groups),
        "duplicate_groups_multi": len(multi_groups),
        "records_in_multi_groups": sum(g["size"] for g in multi_groups),
        "cross_source_groups": sum(
            1 for g in groups if len({m["source_id"] for m in g["members"]}) > 1
        ),
        "normalization": NORMALIZATION_PARAMS,
        "taxonomy": "taxonomy_v1",
        "dedupe": {"similarity_threshold": 0.90, "layers": ["content_hash", "title_similarity"]},
    }

    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    out = MANIFEST_DIR / f"corpus_{version}.yaml"
    if out.exists():
        print(f"{out.name} already exists - corpus versions are immutable; use a new --version")
        raise SystemExit(1)
    out.write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"frozen {manifest['corpus']}: {len(records)} records, sha256={data_hash[:16]}... -> {out}")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Freeze a corpus version")
    parser.add_argument("--version", default="v1")
    args = parser.parse_args(argv)
    freeze(args.version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
