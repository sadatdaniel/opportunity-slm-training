"""Dataset builder (build brief sections 19, 20, 33).

Turns annotated records into versioned, immutable datasets per capability:

    datasets/<task>/<version>/{train,validation,test,unseen_sources_test}.jsonl
    datasets/<task>/<version>/manifest.yaml

Rules enforced here:

- quality tiers: gold (human-approved/corrected) > silver (teacher, no flags)
  > quarantine (flagged or unparsable teacher output; never trained on)
- duplicate groups never span splits (leakage prevention, brief section 14/20)
- an unseen-source evaluation split holds out entire sources
- the test split is frozen: its records are chosen deterministically and the
  manifest records split hashes; later versions never mutate earlier ones.

Usage::

    python -m project.build_dataset --task classify
    python -m project.build_dataset --task summarize --version v1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANNOTATION_DIR = PROJECT_ROOT / "data" / "annotations"
GROUPS_PATH = PROJECT_ROOT / "data" / "manifests" / "duplicate_groups.json"
DATASETS_DIR = PROJECT_ROOT / "datasets"
NORMALIZED_PATH = PROJECT_ROOT / "data" / "normalized" / "deduped.jsonl"

TAXONOMY_CONFIG = PROJECT_ROOT / "config" / "taxonomy_v1.yaml"
# annotation task name -> dataset capability directory (brief 28 layout)
CAPABILITY_DIR = {"classify": "classifier", "summarize": "summarizer"}
SPLIT_RATIOS = {"train": 0.8, "validation": 0.1, "test": 0.1}
UNSEEN_SOURCES_FRACTION = 0.15  # of sources, held out entirely
SEED = 42


def stable_rank(record_id: str, salt: str) -> int:
    """Deterministic shuffle: hash rank instead of random module state."""
    return int.from_bytes(hashlib.sha1(f"{salt}:{record_id}".encode()).digest()[:8], "big")


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def quality_tier(annotation: dict) -> str:
    parsed = annotation.get("parsed_annotation")
    if parsed is None:
        return "quarantine"
    # review UI saves "approve"; normalize here for robustness
    if annotation.get("review_status") in ("approved", "approve", "corrected"):
        return "gold"
    # any warning flag from the teacher keeps it out of silver
    if annotation.get("needs_human_review"):
        return "quarantine"
    return "silver"


def group_map() -> dict[str, str]:
    """record_id -> canonical representative id (duplicate groups act as one)."""
    mapping: dict[str, str] = {}
    if GROUPS_PATH.exists():
        for group in json.loads(GROUPS_PATH.read_text(encoding="utf-8")):
            for member in group["members"]:
                mapping[member["record_id"]] = group["canonical_record_id"]
    return mapping


def assign_splits(records: list[dict], task: str) -> tuple[dict[str, list[dict]], list[str]]:
    """Split by duplicate-group, holding out whole sources for the unseen eval."""
    mapping = group_map()
    by_group: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        by_group[mapping.get(rec["record_id"], rec["record_id"])].append(rec)

    sources = sorted({rec["source_id"] for rec in records})
    held_out = {
        s for s in sources
        if stable_rank(s, f"{task}:unseen:{SEED}") % 1000 < UNSEEN_SOURCES_FRACTION * 1000
    }

    unseen, pool = [], []
    for group_records in by_group.values():
        if any(r["source_id"] in held_out for r in group_records):
            unseen.extend(group_records)
        else:
            pool.extend(group_records)

    ordered = sorted(pool, key=lambda r: stable_rank(mapping.get(r["record_id"], r["record_id"]), f"{task}:split:{SEED}"))
    n = len(ordered)
    cuts = {
        "train": ordered[: int(n * SPLIT_RATIOS["train"])],
        "validation": ordered[int(n * SPLIT_RATIOS["train"]): int(n * (SPLIT_RATIOS["train"] + SPLIT_RATIOS["validation"]))],
        "test": ordered[int(n * (SPLIT_RATIOS["train"] + SPLIT_RATIOS["validation"])):],
    }
    # duplicate groups are kept together: any group straddling a cut moves to
    # the split of its first member
    splits: dict[str, list[dict]] = {"train": [], "validation": [], "test": [], "unseen_sources_test": unseen}
    placed: dict[str, str] = {}
    for split, rows in cuts.items():
        for rec in rows:
            gid = mapping.get(rec["record_id"], rec["record_id"])
            placed.setdefault(gid, split)
    for gid, split in placed.items():
        splits[split].extend(by_group[gid])
    return splits, sorted(held_out)


def training_example(task: str, record: dict, annotation: dict) -> dict | None:
    parsed = annotation.get("parsed_annotation")
    if parsed is None:
        return None
    if task == "summarize":
        target = parsed.get("summary")
        if not target or not isinstance(target, str):
            return None
        return {
            "input": f'TITLE: {record["title"]}\n\nOPPORTUNITY TEXT:\n{record["clean_text"]}',
            "target": target,
        }
    target = parsed.get("primary_category")
    if target not in yaml.safe_load(TAXONOMY_CONFIG.read_text(encoding="utf-8"))["categories"]:
        return None
    return {
        "input": f'TITLE: {record["title"]}\n\nOPPORTUNITY TEXT:\n{record["clean_text"]}',
        "target": target,
        "secondary": parsed.get("secondary_plausible_categories", []),
        "ambiguity": parsed.get("classification_ambiguity"),
    }


def entry_rank(entry: dict) -> int:
    """Quality rank for deduplicating repeated annotation entries per record."""
    if entry.get("review_status"):
        return 3  # human-reviewed beats everything
    if entry.get("status") == "completed":
        return 2
    if entry.get("parsed_annotation") is not None:
        return 1  # e.g. needs_review with a usable teacher label
    return 0  # error / rate_limited stubs


def build(task: str, version: str) -> Path:
    entries = load_jsonl(ANNOTATION_DIR / f"{task}.jsonl")
    # dedupe by record_id, keeping the highest-quality entry per record:
    # reviewed > completed-with-label > label-but-needs-review > stubs
    annotations: dict[str, dict] = {}
    for entry in entries:
        rid = entry["record_id"]
        existing = annotations.get(rid)
        if existing is None or entry_rank(entry) > entry_rank(existing):
            annotations[rid] = entry
    records = {r["record_id"]: r for r in load_jsonl(NORMALIZED_PATH)}
    if not annotations:
        print(f"no annotations found in {ANNOTATION_DIR / f'{task}.jsonl'} — run project.annotate first")
        raise SystemExit(1)

    tiered: dict[str, list[dict]] = {"gold": [], "silver": [], "quarantine": []}
    for rid, ann in annotations.items():
        record = records.get(rid)
        if record is None:
            continue
        tiered[quality_tier(ann)].append((record, ann))

    trainable = [x for tier in ("gold", "silver") for x in tiered[tier]]
    pairs, skipped = [], []
    for record, ann in trainable:
        example = training_example(task, record, ann)
        (pairs if example else skipped).append((record, ann, example))

    split_records, held_out_sources = assign_splits(
        [record for record, _, _ in pairs], task
    )
    by_id = {record["record_id"]: example for record, _, example in pairs}

    out_dir = DATASETS_DIR / CAPABILITY_DIR[task] / version
    if (out_dir / "manifest.yaml").exists():
        print(f"datasets/{CAPABILITY_DIR[task]}/{version} is already frozen — dataset versions are immutable; use a new version")
        raise SystemExit(1)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "task": task,
        "dataset": f"{task}_dataset_{version}",
        "version": version,
        "created_at": datetime.now(UTC).isoformat(),
        "seed": SEED,
        "taxonomy": "taxonomy_v1" if task == "classify" else None,
        "held_out_sources": held_out_sources,
        "splits": {},
        "tiers_used": {"gold": len(tiered["gold"]), "silver": len(tiered["silver"]),
                        "quarantine_excluded": len(tiered["quarantine"]),
                        "skipped_invalid_target": len(skipped)},
    }
    for split, rows in split_records.items():
        path = out_dir / f"{split}.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for record in rows:
                example = by_id.get(record["record_id"])
                if example:
                    fh.write(json.dumps({"record_id": record["record_id"], "source_id": record["source_id"], **example}, ensure_ascii=False) + "\n")
        data = path.read_bytes()
        manifest["splits"][split] = {
            "file": str(path.relative_to(PROJECT_ROOT)),
            "examples": sum(1 for line in data.decode("utf-8").splitlines() if line.strip()),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    (out_dir / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    print(json.dumps(manifest["splits"], indent=1))
    print(f"tiers: {manifest['tiers_used']}")
    return out_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build versioned datasets")
    parser.add_argument("--task", choices=["summarize", "classify"], required=True)
    parser.add_argument("--version", default="v1")
    args = parser.parse_args(argv)
    build(args.task, args.version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
