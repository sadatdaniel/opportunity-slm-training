"""Noul prototype dataset builder (v3 brief step 7B).

Builds a small evaluation/prototype Noul set from corpus_v1 records plus
pilot teacher labels and source metadata. Labels here are DERIVED (a record's
own category as the true case; a sampled different category as the hard-ish
negative; WP deadline metadata for deadline_stated) — suitable for
prototyping the protocol and benchmarking mechanics, NOT as final training
truth. Final Noul training data comes from the reviewed extraction pass.

Every item carries a positive/negative/qualified tag where applicable.

Usage::

    python -m project.build_noul_set                 # -> data/curated/noul_prototype_v0.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter

import yaml

from project.freeze_corpus import PROJECT_ROOT

DEDUPED_PATH = PROJECT_ROOT / "data" / "normalized" / "deduped.jsonl"
ANNOTATIONS_PATH = PROJECT_ROOT / "data" / "annotations" / "classify.jsonl"
FAMILIES_PATH = PROJECT_ROOT / "config" / "noul_families.yaml"
OUT_PATH = PROJECT_ROOT / "data" / "curated" / "noul_prototype_v0.jsonl"

CATEGORIES = ["scholarships", "fellowships", "internships", "competitions", "workshops"]


def build(max_records: int | None = None, seed: int = 42) -> list[dict]:
    families = yaml.safe_load(FAMILIES_PATH.read_text(encoding="utf-8"))["families"]
    records = {
        json.loads(line)["record_id"]: json.loads(line)
        for line in DEDUPED_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    annotations = {}
    if ANNOTATIONS_PATH.exists():
        for line in ANNOTATIONS_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entry = json.loads(line)
                parsed = entry.get("parsed_annotation")
                if entry.get("status") == "completed" and parsed and not entry.get("needs_human_review"):
                    annotations[entry["record_id"]] = parsed

    rng = random.Random(seed)
    items: list[dict] = []
    record_ids = sorted(annotations)
    if max_records:
        record_ids = record_ids[:max_records]

    for rid in record_ids:
        record = records.get(rid)
        parsed = annotations[rid]
        category = parsed.get("primary_category")
        if record is None or category not in CATEGORIES:
            continue
        base = {
            "record_id": rid,
            "source_id": record["source_id"],
            "canonical_url": record["canonical_url"],
            "title": record["title"],
            "state": record["clean_text"][:6000],
            "label_origin": "teacher_pilot",
        }
        family = families[f"category_{category}"]
        items.append({
            **base,
            "item_id": f"{rid}:category_{category}:true",
            "family": f"category_{category}",
            "question": {"type": "noul", "instructions": family["instructions"], "criteria": family["criteria"]},
            "target": True,
            "case": "positive",
        })
        # hard-ish negative: a different category, prefer a confusable neighbor
        neighbors = {
            "scholarships": ["fellowships", "grants"],
            "fellowships": ["scholarships", "postdoc" if "postdoc" in families else "internships"],
            "internships": ["fellowships", "workshops"],
            "competitions": ["awards" if "awards" in families else "workshops", "conferences"],
            "workshops": ["conferences", "competitions"],
        }
        negative = rng.choice(neighbors[category])
        if negative in families:  # e.g. postdoc/awards families exist but no category_ entry
            family_neg = families[negative]
        elif f"category_{negative}" in families:
            family_neg = families[f"category_{negative}"]
        else:
            continue
        items.append({
            **base,
            "item_id": f"{rid}:category_{negative}:false",
            "family": family_neg and f"category_{negative}".replace("category_", "category_"),
            "question": {"type": "noul", "instructions": family_neg["instructions"], "criteria": family_neg["criteria"]},
            "target": False,
            "case": "negative",
        })
        # deadline family from source metadata where the WP field exists
        deadline = (record.get("deadline") or "").strip()
        family_deadline = families["deadline_stated"]
        items.append({
            **base,
            "item_id": f"{rid}:deadline_stated:{'true' if deadline else 'false'}",
            "family": "deadline_stated",
            "question": {"type": "noul", "instructions": family_deadline["instructions"], "criteria": family_deadline["criteria"]},
            "target": bool(deadline),
            "case": "qualified" if deadline else "negative",
            "evidence": deadline or None,
        })

    return items


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Noul prototype set")
    parser.add_argument("--max-records", type=int, default=None)
    args = parser.parse_args(argv)

    items = build(args.max_records)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")

    stats = Counter((item["family"], item["target"]) for item in items)
    print(f"wrote {len(items)} items -> {OUT_PATH}")
    for (family, target), count in sorted(stats.items()):
        print(f"  {family:28} target={target!s:5} {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
