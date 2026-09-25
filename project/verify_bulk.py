"""Bulk independent verification: relabel a task's corpus with a strong model.

Unlike the pilot second-pass (flagged records only), this relabels EVERY
record and flags disagreements with the stored teacher label. Disagreement
volume per (teacher_label, verifier_label) pair is the input to the
taxonomy-v2 decision and the dataset-v4 cleaning cycle.

Usage::

    python -m project.verify_bulk --task classify --provider experiential --model gpt-6-astra
    python -m project.verify_bulk --task classify --resume
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import yaml

from project.annotate import build_messages, input_hash, parse_annotation
from project.freeze_corpus import PROJECT_ROOT
from project.teachers import TeacherPool, load_env

ANNOTATION_DIR = PROJECT_ROOT / "data" / "annotations"
TAXONOMY_CATEGORIES = set(
    yaml.safe_load((PROJECT_ROOT / "config" / "taxonomy_v1.yaml").read_text(encoding="utf-8"))["categories"]
)


def verify_one(pool: TeacherPool, task: str, record: dict, stored_label) -> dict:
    spec, raw = pool.call(build_messages(task, record), roles=["second_opinion", "verifier", "primary"])
    parsed = parse_annotation(raw)
    label = (parsed or {}).get("primary_category") if isinstance(parsed, dict) else None
    valid = "valid" if label in TAXONOMY_CATEGORIES else "invalid"
    return {
        "record_id": record["record_id"],
        "task": task,
        "stored_label": stored_label,
        "verifier": spec["name"],
        "verifier_model": spec["model"],
        "verifier_label": label,
        "verifier_validation": valid,
        "verifier_reason": (parsed or {}).get("reason_for_label") if isinstance(parsed, dict) else None,
        "input_hash": input_hash(record),
        "agreement": stored_label == label if valid == "valid" else None,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bulk corpus verification")
    parser.add_argument("--task", choices=["classify", "summarize"], default="classify")
    parser.add_argument("--provider", default="experiential", help="provider name substring")
    parser.add_argument("--model", default="gpt-6-astra")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--resume", action="store_true", help="skip records already verified")
    parser.add_argument("--skip-consensus", action="store_true",
                        help="skip records already human-decided or verifier-confirmed (spend credit only where it changes outcomes)")
    args = parser.parse_args(argv)
    load_env()

    records = {
        json.loads(l)["record_id"]: json.loads(l)
        for l in (PROJECT_ROOT / "data" / "normalized" / "deduped.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    }
    entries = [
        json.loads(l)
        for l in (ANNOTATION_DIR / f"{args.task}.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    latest: dict[str, dict] = {}
    for entry in entries:
        if entry.get("status") == "completed" and entry.get("parsed_annotation"):
            latest[entry["record_id"]] = entry

    out_path = ANNOTATION_DIR / f"verify_bulk_{args.task}.jsonl"
    done: set[str] = set()
    if args.resume and out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(json.loads(line)["record_id"])

    skip: set[str] = set()
    if args.skip_consensus:
        consensus_path = ANNOTATION_DIR / f"consensus_{args.task}.jsonl"
        if consensus_path.exists():
            for line in consensus_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                basis = row.get("basis", "")
                if basis.startswith("human_") or basis.startswith("confirmed"):
                    skip.add(row["record_id"])
    targets = [
        (rid, entry) for rid, entry in latest.items()
        if rid in records and rid not in done and rid not in skip
    ]
    print(f"verifying {len(targets)} records with {args.provider}/{args.model}, workers={args.workers}", flush=True)

    pool = TeacherPool()
    pool.providers = [p for p in pool.providers if args.provider in p["name"]]
    for spec in pool.providers:
        spec["model"] = args.model  # override to the requested model
    if not pool.providers:
        print("no matching provider")
        return 1

    write_lock = threading.Lock()
    results: list[dict] = []
    # ThreadPoolExecutor queues internally; submitting all upfront is safe
    with out_path.open("a" if args.resume else "w", encoding="utf-8") as out:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(
                    verify_one, pool, args.task, records[rid],
                    (entry.get("parsed_annotation") or {}).get("primary_category"),
                ): rid
                for rid, entry in targets
            }
            for index, future in enumerate(as_completed(futures), 1):
                rid = futures[future]
                try:
                    outcome = future.result()
                except Exception as exc:  # noqa: BLE001
                    outcome = {"record_id": rid, "error": f"{type(exc).__name__}: {exc}"[:150]}
                with write_lock:
                    out.write(json.dumps(outcome, ensure_ascii=False) + "\n")
                    out.flush()
                results.append(outcome)
                if index % 100 == 0:
                    print(f"  {index}/{len(futures)}", flush=True)

    valid = [r for r in results if r.get("verifier_validation") == "valid"]
    agree = sum(1 for r in valid if r.get("agreement"))
    pairs = Counter((r["stored_label"], r["verifier_label"]) for r in valid if r.get("agreement") is False)
    print(json.dumps({
        "verified": len(valid),
        "agreement_rate": round(agree / len(valid), 3) if valid else None,
        "top_disagreements": [f"{a} -> {b}: {n}" for (a, b), n in pairs.most_common(10)],
    }, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
