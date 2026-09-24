"""Normalization and cleaning (build brief section 13).

Reads raw collected records, detects language, applies a deterministic
cleaning pass that strips obvious boilerplate (cookie notices, share widgets,
subscription prompts, excessive whitespace) while PRESERVING meaningful
sections like Eligibility / Benefits / Deadline.

Usage::

    python -m project.normalize            # raw -> data/normalized/records.jsonl
    python -m project.normalize --report   # rebuild the markdown report only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
NORMALIZED_PATH = PROJECT_ROOT / "data" / "normalized" / "records.jsonl"
REPORT_PATH = PROJECT_ROOT / "reports" / "normalization_report.md"

MIN_WORDS = 40  # shorter than this is not a usable opportunity posting

# English-likeness heuristic: coverage of high-frequency words. Avoids adding
# a language-detection dependency; good enough to filter obvious non-English.
_EN_STOPWORDS = {
    "the", "and", "of", "to", "in", "for", "is", "are", "be", "on", "or", "with",
    "as", "at", "an", "will", "by", "this", "that", "from", "you", "your", "their",
    "a", "not", "have", "has", "must", "may", "can", "which", "who", "students",
    "applications", "application", "deadline", "programme", "program", "research",
}
NOISE_PATTERNS = [
    re.compile(r"(?im)^\s*(share (this|on)|tweet|like this:?|related (posts|articles?)|"
               r"you may also like|leave a (reply|comment)|click to share|whatsapp|"
               r"telegram|facebook|x\b|linkedin|pinterest|email|print|more)[:!.]?\s*$"),
    re.compile(r"(?im)^\s*(subscribe|sign up|follow us|join our|download now|"
               r"we use cookies?|cookie (policy|notice)|accept all|privacy policy|"
               r"terms of (use|service)|all rights reserved|copyright ©?).*$"),
    re.compile(r"(?im)^\s*\d+\s*shares?\s*$"),
    re.compile(r"(?im)^\s*(advertisement|sponsored|recommended for you)\s*$"),
]


def is_english(text: str) -> bool:
    words = re.findall(r"[a-z']+", text.lower())
    if not words:
        return False
    hits = sum(1 for w in words if w in _EN_STOPWORDS)
    return hits / len(words) >= 0.22


def clean_text(text: str) -> str:
    lines = text.splitlines()
    kept = []
    for line in lines:
        stripped = line.strip()
        if any(pat.match(stripped) for pat in NOISE_PATTERNS):
            continue
        kept.append(stripped)
    out = "\n".join(kept)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def word_count(text: str) -> int:
    return len(text.split())


def normalize_record(record: dict) -> dict | None:
    clean = clean_text(record.get("clean_text") or "")
    if not clean:
        return None
    n_words = word_count(clean)
    if n_words < MIN_WORDS:
        return None
    out = dict(record)
    out["clean_text"] = clean
    out["language"] = "en" if is_english(f"{record.get('title', '')} {clean}") else "other"
    out["word_count"] = n_words
    return out


def run_normalize() -> dict:
    stats: Counter = Counter()
    by_source: Counter = Counter()
    NORMALIZED_PATH.parent.mkdir(parents=True, exist_ok=True)
    with NORMALIZED_PATH.open("w", encoding="utf-8") as out:
        for raw_file in sorted(RAW_DIR.glob("*/*.jsonl")):
            source_id = raw_file.parent.name
            for line in raw_file.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                stats["raw_seen"] += 1
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    stats["unparseable"] += 1
                    continue
                normalized = normalize_record(record)
                if normalized is None:
                    stats["dropped_empty_or_short"] += 1
                    continue
                if normalized["language"] != "en":
                    stats["dropped_non_english"] += 1
                    continue
                stats["kept"] += 1
                by_source[source_id] += 1
                out.write(json.dumps(normalized, ensure_ascii=False) + "\n")
    return {"stats": dict(stats), "by_source": dict(by_source)}


def write_report(results: dict) -> None:
    stats, by_source = results["stats"], results["by_source"]
    lines = [
        "# Normalization Report",
        "",
        f"- raw records seen: {stats.get('raw_seen', 0)}",
        f"- kept (English, >= {MIN_WORDS} words): {stats.get('kept', 0)}",
        f"- dropped empty/short: {stats.get('dropped_empty_or_short', 0)}",
        f"- dropped non-English: {stats.get('dropped_non_english', 0)}",
        f"- unparseable lines: {stats.get('unparseable', 0)}",
        "",
        "## Kept per source",
        "",
        "| source | records |",
        "|---|---|",
    ]
    for source_id, count in sorted(by_source.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {source_id} | {count} |")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Normalize raw records")
    parser.add_argument("--report", action="store_true", help="rebuild report only")
    args = parser.parse_args(argv)
    if not args.report:
        results = run_normalize()
        print(json.dumps(results["stats"]))
    else:
        by_source: Counter = Counter()
        if NORMALIZED_PATH.exists():
            for line in NORMALIZED_PATH.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    by_source[json.loads(line)["source_id"]] += 1
        results = {"stats": {"kept": sum(by_source.values())}, "by_source": dict(by_source)}
    write_report(results)
    print(f"normalized records: {NORMALIZED_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
