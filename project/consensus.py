"""Consensus engine: merge all verification sources into final labels.

Sources, in authority order:
1. human decisions (review_status approved/corrected/reject)  -> GOLD, final
2. verifier 2-of-3: if two independent verifications agree, that label wins
3. single verifier agreeing with teacher                           -> confirmed
4. single verifier disagreeing with teacher                        -> UNRESOLVED
   -> needs human review (or a third-opinion run)
5. never verified                                                  -> teacher
   label stands as silver, record goes on the to-verify list

Emits ``data/annotations/consensus_classify.jsonl`` — one overlay entry per
record: {record_id, final_label, basis, needs_human_review}. The dataset
builder applies the overlay: final_label replaces the teacher label, and
needs_human_review entries quarantine.

Also emits the to-verify list (never-verified + unresolved) so verification
credit is spent ONLY where it changes outcomes — never re-verifying
already-confirmed records.

Usage::

    python -m project.consensus --task classify
    python -m project.consensus --task classify --emit-verify-list
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from project.annotate import load_taxonomy
from project.freeze_corpus import PROJECT_ROOT

ANNOTATION_DIR = PROJECT_ROOT / "data" / "annotations"
CONSENSUS_PATH = ANNOTATION_DIR / "consensus_{task}.jsonl"
TO_VERIFY_PATH = ANNOTATION_DIR / "to_verify_{task}.jsonl"


def load_latest(path: Path, id_field: str = "record_id") -> dict[str, dict]:
    latest: dict[str, dict] = {}
    if not path.exists():
        return latest
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        key = row[id_field]
        stamp = row.get("reviewed_at") or row.get("verified_at") or row.get("teacher_timestamp") or ""
        if key not in latest or stamp > (latest[key].get("reviewed_at") or latest[key].get("verified_at") or latest[key].get("teacher_timestamp") or ""):
            latest[key] = row
    return latest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge verification sources into consensus labels")
    parser.add_argument("--task", choices=["summarize", "classify"], default="classify")
    parser.add_argument("--emit-verify-list", action="store_true", help="also write records still needing verification")
    args = parser.parse_args(argv)

    categories = set(load_taxonomy())

    # 1. teacher annotations + human decisions (latest wins)
    annotations = load_latest(ANNOTATION_DIR / f"{args.task}.jsonl")

    # 2. human decisions elevate to gold
    # 3. independent verifications (any number of sources)
    verifier_sources = {}
    for name in ("verify_bulk", "verify"):
        p = ANNOTATION_DIR / f"{name}_{args.task}.jsonl"
        if p.exists():
            verifier_sources[name] = load_latest(p, "record_id")

    records = {
        json.loads(l)["record_id"]: json.loads(l)
        for l in (PROJECT_ROOT / "data" / "normalized" / "deduped.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    }

    consensus_path = Path(str(CONSENSUS_PATH).format(task=args.task))
    to_verify_path = Path(str(TO_VERIFY_PATH).format(task=args.task))

    stats: Counter = Counter()
    overlay_rows: list[dict] = []
    to_verify: list[str] = []

    for rid, record in records.items():
        ann = annotations.get(rid)
        teacher_label = (ann.get("parsed_annotation") or {}).get("primary_category") if ann else None
        if ann is None:
            stats["no_annotation"] += 1
            continue

        # GOLD: human decision is final
        if ann.get("review_status") in ("approved", "approve", "corrected"):
            overlay_rows.append({
                "record_id": rid,
                "final_label": (ann.get("parsed_annotation") or {}).get("primary_category"),
                "basis": f"human_{ann['review_status']}",
                "needs_human_review": False,
            })
            stats["gold_human"] += 1
            continue
        if ann.get("review_status") == "reject":
            overlay_rows.append({"record_id": rid, "final_label": None, "basis": "human_reject",
                                 "needs_human_review": False})
            stats["gold_rejected"] += 1
            continue

        # verifier verdicts
        verdicts = []
        for source_name, source in verifier_sources.items():
            v = source.get(rid)
            if v and v.get("verifier_validation") == "valid":
                verdicts.append((source_name, v.get("verifier_label")))

        if not verdicts:
            # teacher label stands as silver; queue for verification
            overlay_rows.append({"record_id": rid, "final_label": teacher_label,
                                 "basis": "teacher_unverified", "needs_human_review": False})
            stats["unverified_silver"] += 1
            to_verify.append(rid)
            continue

        agree = [label for _, label in verdicts if label == teacher_label]
        disagree = [label for _, label in verdicts if label != teacher_label]

        if not disagree:
            # all verifiers confirm the teacher
            overlay_rows.append({"record_id": rid, "final_label": teacher_label,
                                 "basis": "confirmed_" + "+".join(s for s, _ in verdicts),
                                 "needs_human_review": False})
            stats["confirmed"] += 1
        elif len(disagree) >= len(verdicts) - len(agree) and disagree:
            # verifier(s) disagree with teacher
            disagreement_label = Counter(disagree).most_common(1)[0][0]
            disagree_votes = Counter(disagree).most_common(1)[0][1]
            if disagree_votes >= 2:
                # 2+ verifiers agree on a different label: teacher was wrong
                overlay_rows.append({"record_id": rid, "final_label": disagreement_label,
                                     "basis": f"consensus_2of3_{disagreement_label}",
                                     "needs_human_review": True})
                stats["overruled_2of3"] += 1
            elif len(verdicts) >= 2:
                # split verdicts: genuinely contested
                overlay_rows.append({"record_id": rid, "final_label": teacher_label,
                                     "basis": "split_verdicts", "needs_human_review": True})
                stats["split_needs_human"] += 1
            else:
                # single dissenting verifier: unresolved -> human review
                overlay_rows.append({"record_id": rid, "final_label": teacher_label,
                                     "basis": f"single_disagreement_{verdicts[0][0]}",
                                     "needs_human_review": True})
                stats["single_disagreement"] += 1
                to_verify.append(rid)  # worth a third opinion
        else:
            overlay_rows.append({"record_id": rid, "final_label": teacher_label,
                                 "basis": "mixed_majority", "needs_human_review": False})
            stats["mixed_majority"] += 1

    consensus_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in overlay_rows) + "\n", encoding="utf-8"
    )
    if args.emit_verify_list:
        to_verify_path.write_text(
            "\n".join(json.dumps({"record_id": rid}) for rid in to_verify) + "\n", encoding="utf-8"
        )

    print(json.dumps({"consensus": dict(stats), "to_verify": len(to_verify) if args.emit_verify_list else None}))
    print(f"overlay -> {consensus_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
