"""Independent verification of teacher annotations (brief 17A: teacher-agreement checks).

Re-labels unflagged pilot annotations with an independent provider
(deepseek-flash) that sees the same task with no hint of the existing label,
then compares. Agreement estimates the silver error rate; disagreements join
the human review queue.

DeepSeek documents concurrency limits rather than RPM (2500 simultaneous for
deepseek-flash), so records run as CONCURRENT per-record requests with a high
worker count taken from the provider's max_concurrency.

Usage::

    python -m project.verify_annotations                    # all unflagged records
    python -m project.verify_annotations --workers 32       # override concurrency
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime

import yaml

from project.annotate import build_messages, input_hash, parse_annotation
from project.freeze_corpus import PROJECT_ROOT
from project.teachers import TeacherPool, load_env

ANNOTATIONS_PATH = PROJECT_ROOT / "data" / "annotations" / "classify.jsonl"
VERIFY_PATH = PROJECT_ROOT / "data" / "annotations" / "verify_classify.jsonl"
TAXONOMY_CATEGORIES = set(
    yaml.safe_load((PROJECT_ROOT / "config" / "taxonomy_v1.yaml").read_text(encoding="utf-8"))["categories"]
)


def verify_one(pool: TeacherPool, task: str, entry: dict, record: dict) -> dict:
    outcome: dict = {
        "record_id": entry["record_id"],
        "verify_task": task,
        "original_label": (entry.get("parsed_annotation") or {}).get("primary_category"),
        "original_provider": entry.get("teacher_provider_slot"),
        "input_hash": input_hash(record),
        "started_at": datetime.now(UTC).isoformat(),
    }
    spec, raw = pool.call(build_messages(task, record), roles=["verifier", "second_opinion"])
    parsed = parse_annotation(raw)
    label = (parsed or {}).get("primary_category") if isinstance(parsed, dict) else None
    valid = "valid" if label in TAXONOMY_CATEGORIES else "invalid"
    outcome.update(
        verifier=spec["name"],
        verifier_model=spec["model"],
        verifier_label=label,
        verifier_validation=valid,
        verifier_reason=(parsed or {}).get("reason_for_label") if isinstance(parsed, dict) else None,
        completed_at=datetime.now(UTC).isoformat(),
    )
    outcome["agreement"] = outcome["original_label"] == label if valid == "valid" else None
    return outcome


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Independent annotation verification (concurrent)")
    parser.add_argument("--task", choices=["classify", "summarize"], default="classify")
    parser.add_argument("--workers", type=int, default=None, help="override provider max_concurrency")
    parser.add_argument("--per-category", type=int, default=None, help="cap records per category (default: all)")
    args = parser.parse_args(argv)
    load_env()

    entries = [
        json.loads(line)
        for line in ANNOTATIONS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    unique: dict[str, dict] = {}
    for entry in entries:
        rid = entry["record_id"]
        if entry.get("status") == "completed" and entry.get("validation_status") == "valid" and not entry.get("needs_human_review"):
            if rid not in unique:
                unique[rid] = entry
    targets = list(unique.values())
    if args.per_category:
        by_category: dict[str, list[dict]] = defaultdict(list)
        for e in targets:
            by_category[(e.get("parsed_annotation") or {}).get("primary_category")].append(e)
        targets = [e for cat in sorted(by_category) for e in by_category[cat][: args.per_category]]
    print(f"verifying {len(targets)} unflagged annotations concurrently", flush=True)

    records = {
        json.loads(line)["record_id"]: json.loads(line)
        for line in (PROJECT_ROOT / "data" / "normalized" / "deduped.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }

    pool = TeacherPool()
    if not pool.providers:
        print("no providers configured")
        return 1
    workers = args.workers or next(
        (p.get("max_concurrency", 16) for p in pool.providers if p.get("role") == "verifier"), 16
    )
    print(f"workers: {workers}", flush=True)

    VERIFY_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_lock = threading.Lock()
    results: list[dict] = []

    with VERIFY_PATH.open("w", encoding="utf-8") as out, ThreadPoolExecutor(max_workers=workers) as pool_executor:
        futures = {
            pool_executor.submit(verify_one, pool, args.task, entry, records[entry["record_id"]]): entry
            for entry in targets
            if entry["record_id"] in records
        }
        for index, future in enumerate(as_completed(futures), 1):
            try:
                outcome = future.result()
            except Exception as exc:  # noqa: BLE001 - record per-record failures
                entry = futures[future]
                outcome = {
                    "record_id": entry["record_id"],
                    "verify_task": args.task,
                    "error": f"{type(exc).__name__}: {exc}"[:200],
                    "completed_at": datetime.now(UTC).isoformat(),
                }
            with write_lock:
                out.write(json.dumps(outcome, ensure_ascii=False) + "\n")
                out.flush()
            results.append(outcome)
            if index % 25 == 0:
                print(f"  {index}/{len(futures)}", flush=True)
    pool.save_state()

    done = [r for r in results if r.get("verifier_validation") == "valid"]
    agree = sum(1 for r in done if r.get("agreement"))
    print(json.dumps({
        "verified": len(done),
        "errors": len(results) - len(done),
        "agreement": agree,
        "agreement_rate": round(agree / len(done), 3) if done else None,
    }))
    for r in done:
        if r.get("agreement") is False:
            print(f"  DISAGREE {r['original_label']} -> {r['verifier_label']} | {r['record_id'][:8]}")
    print(f"details -> {VERIFY_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
