"""Teacher annotation with multi-provider routing (v2 brief sections 15, 17, 17A, 17B).

Routing (guideline, not three calls per record):
    normal record -> primary teacher (Gemini slots, cheapest first)
      clean + schema-valid + unambiguous  -> SAVE
      ambiguous / schema-invalid          -> second opinion (OpenRouter)
        strong agreement (classify: same primary_category) -> SAVE with note
        disagreement -> adjudicator suggestion (Z.ai GLM) recorded -> review flag

Resumability: every completed annotation is appended to
``data/annotations/<task>.jsonl`` immediately; re-runs skip completed records
and retry errored ones. Each entry carries full provenance (provider, model,
credential slot name, prompt/schema versions, input hash) so stale
annotations are detectable — dataset building skips entries whose
prompt_version, taxonomy_version, or input_hash no longer match.

Usage::

    python -m project.annotate --task classify --pilot      # ~200 stratified examples
    python -m project.annotate --task summarize --pilot 300
    python -m project.annotate --task classify              # annotate the corpus
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

from project.freeze_corpus import PROJECT_ROOT
from project.teachers import QuotaExhausted, TeacherPool, load_env

DEFAULT_INPUT = PROJECT_ROOT / "data" / "normalized" / "deduped.jsonl"
TAXONOMY_CONFIG = PROJECT_ROOT / "config" / "taxonomy_v1.yaml"
ANNOTATION_DIR = PROJECT_ROOT / "data" / "annotations"
PROMPTS_DIR = PROJECT_ROOT / "prompts"

PROMPT_VERSION = {"summarize": "summarizer_v1", "classify": "classifier_v1"}
SCHEMA_VERSION = 1
MAX_INPUT_WORDS = 600
PILOT_DEFAULT = 200

CANDIDATE_SIGNALS = {
    "scholarships": ["scholarship", "bursary"],
    "fellowships": ["fellowship"],
    "phd": ["phd", "doctoral"],
    "postdoc": ["postdoc"],
    "grants": ["grant"],
    "internships": ["internship"],
    "competitions": ["competition", "hackathon"],
    "awards": ["award", "prize"],
    "conferences": ["conference", "summit"],
    "workshops": ["workshop", "summer school", "training"],
    "exchange_programs": ["exchange"],
}


def input_hash(record: dict) -> str:
    material = f'{record["title"]}\n{record["clean_text"]}'.encode()
    return hashlib.sha256(material).hexdigest()


def load_taxonomy() -> list[str]:
    taxonomy = yaml.safe_load(TAXONOMY_CONFIG.read_text(encoding="utf-8"))
    return list(taxonomy["categories"])


def build_messages(task: str, record: dict) -> list[dict]:
    system = (PROMPTS_DIR / f"{PROMPT_VERSION[task]}.md").read_text(encoding="utf-8")
    if task == "summarize":
        words = " ".join(record["clean_text"].split()[:MAX_INPUT_WORDS])
        user = f'TITLE: {record["title"]}\n\nOPPORTUNITY TEXT:\n{words}'
    else:
        categories = ", ".join(load_taxonomy())
        user = (
            f"CATEGORIES: {categories}\n\nTITLE: {record['title']}\n\n"
            f"OPPORTUNITY TEXT:\n{record['clean_text'][:6000]}"
        )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


# -- validation ---------------------------------------------------------------


def validate(task: str, parsed: dict | None) -> str:
    """Returns 'valid', 'invalid', or 'ambiguous'."""
    if not isinstance(parsed, dict):
        return "invalid"
    if task == "classify":
        if parsed.get("primary_category") not in load_taxonomy():
            return "invalid"
        ambiguity = parsed.get("classification_ambiguity", 0)
        # Only genuinely torn records earn extra API calls; a listed secondary
        # with low stated ambiguity is a review note, not a routing trigger
        # (brief 17A: do not spend multiple calls on easy cases).
        if ambiguity >= 0.6 or (parsed.get("secondary_plausible_categories") and ambiguity >= 0.4):
            return "ambiguous"
        return "valid"
    summary = parsed.get("summary")
    if not isinstance(summary, str) or len(summary.split()) > 180:
        return "invalid"
    if parsed.get("ambiguity_score", 0) >= 0.6:
        return "ambiguous"
    return "valid"


def parse_annotation(raw: str) -> dict | None:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def agreement(task: str, first: dict, second: dict | None) -> str | None:
    """'agree' | 'disagree' | None (not comparable)."""
    if not isinstance(second, dict):
        return None
    if task == "classify":
        return "agree" if first.get("primary_category") == second.get("primary_category") else "disagree"
    return None  # summaries: no cheap agreement test; ambiguity flags steer review


def stratified_sample(records: list[dict], n: int) -> list[dict]:
    """Round-robin over candidate-signal buckets + a no-signal bucket."""
    buckets: dict[str, list[dict]] = {}
    for category, keywords in CANDIDATE_SIGNALS.items():
        buckets[category] = [r for r in records if any(kw in r["title"].lower() for kw in keywords)]
    claimed = {r["record_id"] for rs in buckets.values() for r in rs}
    buckets["no_signal"] = [r for r in records if r["record_id"] not in claimed]
    names = sorted(buckets)
    picked: list[dict] = []
    while len(picked) < n and any(buckets[name] for name in names):
        for name in names:
            if buckets[name] and len(picked) < n:
                picked.append(buckets[name].pop(0))
    return picked


# -- main loop ----------------------------------------------------------------


def entry_base(task: str, record: dict) -> dict:
    return {
        "record_id": record["record_id"],
        "input_hash": input_hash(record),
        "task": task,
        "prompt_version": PROMPT_VERSION[task],
        "schema_version": SCHEMA_VERSION,
        "taxonomy_version": "taxonomy_v1" if task == "classify" else None,
    }


def annotate(task: str, input_path: Path, limit: int | None, pilot: bool) -> int:
    pool = TeacherPool()
    if not pool.providers:
        print(
            "No teacher providers configured. Copy .env.example to .env and set at least\n"
            "  GEMINI_API_KEY (slots GEMINI_API_KEY..GEMINI_API_KEY4 supported)\n"
            "or OPENROUTER_API_KEY / ZAI_API_KEY / legacy TEACHER_* variables."
        )
        return 1

    records = [
        json.loads(line)
        for line in input_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if pilot:
        records = stratified_sample(records, limit or PILOT_DEFAULT)
    elif limit:
        records = records[:limit]

    out_path = ANNOTATION_DIR / f"{task}.jsonl"
    ANNOTATION_DIR.mkdir(parents=True, exist_ok=True)
    done: dict[str, dict] = {}
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entry = json.loads(line)
                if entry.get("status") == "completed":
                    done[entry["record_id"]] = entry

    stats = {"completed": 0, "skipped": 0, "second_opinions": 0, "disagreements": 0, "errors": 0}
    with out_path.open("a", encoding="utf-8") as out:
        for index, record in enumerate(records):
            if record["record_id"] in done:
                stats["skipped"] += 1
                continue
            entry = entry_base(task, record)
            entry["started_at"] = datetime.now(UTC).isoformat()
            entry["attempt_count"] = 1
            try:
                spec, raw = pool.call(build_messages(task, record))
            except QuotaExhausted as exc:
                entry.update(status="rate_limited", error_type=str(exc)[:120])
                out.write(json.dumps(entry, ensure_ascii=False) + "\n")
                stats["errors"] += 1
                print(f"quota exhausted after {index} records; state saved - resume later")
                break
            except Exception as exc:  # noqa: BLE001 - record and continue
                entry.update(status="error", error_type=f"{type(exc).__name__}: {exc}"[:200])
                out.write(json.dumps(entry, ensure_ascii=False) + "\n")
                stats["errors"] += 1
                continue

            parsed = parse_annotation(raw)
            validation = validate(task, parsed)
            flags: list[str] = []
            provider_meta = {
                "teacher_provider": spec["kind"],
                "teacher_provider_slot": spec["name"],
                "teacher_model": spec["model"],
            }

            if validation == "invalid":
                # one second opinion before giving up on the record
                try:
                    spec2, raw2 = pool.call(build_messages(task, record), roles=["second_opinion", "primary"])
                except Exception:  # noqa: BLE001 - fall back to primary result
                    parsed2, provider2 = None, None
                else:
                    parsed2, provider2 = parse_annotation(raw2), spec2
                    stats["second_opinions"] += 1
                if validate(task, parsed2) in ("valid", "ambiguous") and provider2:
                    parsed, raw = parsed2, raw2
                    validation = validate(task, parsed)
                    provider_meta.update(
                        teacher_provider=provider2["kind"],
                        teacher_provider_slot=provider2["name"],
                        teacher_model=provider2["model"],
                    )
                    flags.append("recovered_by_second_opinion")

            if validation == "ambiguous" and task == "classify":
                try:
                    spec3, raw3 = pool.call(build_messages(task, record), roles=["adjudicator", "second_opinion"])
                    adjudication = parse_annotation(raw3)
                    if adjudication:
                        entry["adjudication_suggestion"] = adjudication.get("primary_category")
                        entry["adjudication_provider"] = spec3["name"]
                        outcome = agreement(task, parsed, adjudication)
                        flags.append("adjudicator_" + (outcome or "unparseable"))
                except Exception:  # noqa: BLE001 - adjudication is best-effort
                    flags.append("adjudication_unavailable")

            entry.update(
                status="completed" if validation != "invalid" else "needs_review",
                validation_status=validation,
                review_flags=flags,
                teacher_timestamp=datetime.now(UTC).isoformat(),
                teacher_raw_response=raw,
                parsed_annotation=parsed,
                needs_human_review=validation != "valid" or bool(flags),
                **provider_meta,
            )
            out.write(json.dumps(entry, ensure_ascii=False) + "\n")
            out.flush()
            pool.save_state()
            stats["completed" if entry["status"] == "completed" else "errors"] += 1
            if "disagree" in " ".join(flags):
                stats["disagreements"] += 1
            if (index + 1) % 25 == 0:
                print(f"  {index + 1}/{len(records)} done", flush=True)

    pool.save_state()
    print(json.dumps(stats))
    print(f"annotations -> {out_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Teacher annotation (multi-provider)")
    parser.add_argument("--task", choices=["summarize", "classify"], required=True)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--pilot", action="store_true", help="stratified pilot sample (v2 brief step 5)")
    args = parser.parse_args(argv)
    load_env()
    return annotate(args.task, args.input, args.limit, args.pilot)


if __name__ == "__main__":
    sys.exit(main())
