"""Independent verification of teacher annotations (brief 17A: teacher-agreement checks).

Re-labels a stratified sample of *unflagged* pilot annotations with an
independent provider (deepseek-flash) that sees the same task with no hint of
the existing label, then compares. Agreement estimates the silver error rate;
disagreements join the human review queue. This replaces/adapts the manual
~20-record spot check requested for the step-6 gate.

Usage::

    python -m project.verify_annotations --task classify --per-category 2
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from project.annotate import build_messages, input_hash, parse_annotation, validate
from project.freeze_corpus import PROJECT_ROOT
from project.teachers import QuotaExhausted, TeacherPool, load_env

ANNOTATIONS_PATH = PROJECT_ROOT / "data" / "annotations" / "classify.jsonl"
VERIFY_PATH = PROJECT_ROOT / "data" / "annotations" / "verify_classify.jsonl"


def stratified_sample(entries: list[dict], per_category: int) -> list[dict]:
    by_category: dict[str, list[dict]] = defaultdict(list)
    for entry in entries:
        category = (entry.get("parsed_annotation") or {}).get("primary_category")
        if category:
            by_category[category].append(entry)
    picked: list[dict] = []
    for category in sorted(by_category):
        picked.extend(by_category[category][:per_category])
    return picked


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Independent annotation verification")
    parser.add_argument("--task", choices=["classify", "summarize"], default="classify")
    parser.add_argument("--per-category", type=int, default=2, help="records per category to verify")
    args = parser.parse_args(argv)
    load_env()

    if not ANNOTATIONS_PATH.exists():
        print("no annotations to verify - run the pilot first")
        return 1
    entries = [
        json.loads(line)
        for line in ANNOTATIONS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    # unflagged, valid, completed pilot annotations only
    candidates = [
        e for e in entries
        if e.get("status") == "completed"
        and e.get("validation_status") == "valid"
        and not e.get("needs_human_review")
    ]
    # dedupe by record_id (keep the first completed entry per record)
    seen: set[str] = set()
    unique = []
    for e in candidates:
        if e["record_id"] not in seen:
            seen.add(e["record_id"])
            unique.append(e)
    sample = stratified_sample(unique, args.per_category)
    print(f"verifying {len(sample)} of {len(unique)} unflagged annotations "
          f"({args.per_category}/category)")

    pool = TeacherPool()
    if not pool.providers:
        print("no providers configured")
        return 1

    records = {
        json.loads(line)["record_id"]: json.loads(line)
        for line in (PROJECT_ROOT / "data" / "normalized" / "deduped.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }

    VERIFY_PATH.parent.mkdir(parents=True, exist_ok=True)
    results = []
    with VERIFY_PATH.open("w", encoding="utf-8") as out:
        for index, entry in enumerate(sample):
            record = records.get(entry["record_id"])
            if record is None:
                continue
            outcome: dict = {
                "record_id": entry["record_id"],
                "verify_task": args.task,
                "original_label": (entry.get("parsed_annotation") or {}).get("primary_category"),
                "original_provider": entry.get("teacher_provider_slot"),
                "verifier": None,
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
            try:
                spec, raw = pool.call(build_messages(args.task, record), roles=["verifier", "second_opinion"])
                parsed = parse_annotation(raw)
                outcome.update(
                    verifier=spec["name"],
                    verifier_model=spec["model"],
                    verifier_raw_response=raw,
                    verifier_parsed=parsed,
                    verifier_label=(parsed or {}).get("primary_category"),
                    input_hash=input_hash(record),
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )
                valid = validate(args.task, parsed)
                outcome["verifier_validation"] = valid
                outcome["agreement"] = (
                    outcome["original_label"] == outcome["verifier_label"] if valid == "valid" else None
                )
            except QuotaExhausted as exc:
                outcome.update(error=str(exc)[:200])
                print("quota exhausted; stopping early")
                out.write(json.dumps(outcome, ensure_ascii=False) + "\n")
                break
            except Exception as exc:  # noqa: BLE001 - record and continue
                outcome.update(error=f"{type(exc).__name__}: {exc}"[:200])
            out.write(json.dumps(outcome, ensure_ascii=False) + "\n")
            results.append(outcome)
            if (index + 1) % 6 == 0:
                print(f"  {index + 1}/{len(sample)}", flush=True)
    pool.save_state()

    done = [r for r in results if "error" not in r]
    agree = sum(1 for r in done if r.get("agreement"))
    print(json.dumps({
        "verified": len(done),
        "errors": len(results) - len(done),
        "agreement": agree,
        "agreement_rate": round(agree / len(done), 3) if done else None,
    }))
    disagreements = [r for r in done if r.get("agreement") is False]
    for r in disagreements:
        print(f"  DISAGREE {r['original_label']} -> {r['verifier_label']} | {r['record_id'][:8]}")
    print(f"details -> {VERIFY_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
