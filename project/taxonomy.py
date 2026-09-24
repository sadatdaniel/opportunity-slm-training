"""Taxonomy discovery evidence (build brief section 7).

Mines the collected corpus for category signals — WP categories/tags where
available, plus title keywords — and writes ``reports/proposed_categories.md``
with frequencies and example records. The decision about which categories
become canonical lives in ``config/taxonomy_v1.yaml`` (authored after reading
this evidence), never silently mutated.

Usage::

    python -m project.taxonomy            # uses data/normalized/deduped.jsonl
    python -m project.taxonomy --input data/normalized/records.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "normalized" / "deduped.jsonl"
REPORT_PATH = PROJECT_ROOT / "reports" / "proposed_categories.md"

# Title-keyword signals for records that carry no WP terms (RSS/HTML sources).
TITLE_SIGNALS = {
    "scholarship": "scholarships",
    "fellowship": "fellowships",
    "internship": "internships",
    "competition": "competitions",
    "prize": "competitions",
    "award": "awards",
    "conference": "conferences",
    "summit": "conferences",
    "workshop": "workshops",
    "training": "workshops",
    "exchange": "exchange_programs",
    "grant": "grants",
    "phd": "phd",
    "doctoral": "phd",
    "postdoc": "postdoc",
    "postdoctoral": "postdoc",
    "masters": "masters",
    "summer school": "summer_schools",
}


def title_signals(title: str) -> list[str]:
    title = title.lower()
    found = [canon for kw, canon in TITLE_SIGNALS.items() if kw in title]
    return found or ["no_signal"]


def run(input_path: Path) -> dict:
    records = [
        json.loads(line)
        for line in input_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    wp_terms: Counter = Counter()
    wp_by_source: dict[str, Counter] = defaultdict(Counter)
    title_cues: Counter = Counter()
    examples: dict[str, list] = defaultdict(list)

    for rec in records:
        for term in rec.get("extra", {}).get("wp_categories", []):
            key = term.lower().strip()
            wp_terms[key] += 1
            wp_by_source[rec["source_id"]][key] += 1
        for signal in title_signals(rec.get("title", "")):
            title_cues[signal] += 1
            if len(examples[signal]) < 3:
                examples[signal].append(f'{rec["title"][:90]} ({rec["source_id"]})')

    return {"n": len(records), "wp_terms": wp_terms, "wp_by_source": wp_by_source,
            "title_cues": title_cues, "examples": examples}


def write_report(results: dict, input_path: Path) -> None:
    lines = [
        "# Proposed Categories — corpus evidence",
        "",
        f"Input: `{input_path.relative_to(PROJECT_ROOT)}` ({results['n']} records).",
        "",
        "WP terms and title cues are SIGNALS, not labels (brief section 6): source",
        "scope and site categories describe what a site publishes, not what each",
        "post is. Canonical decisions go to `config/taxonomy_v1.yaml`.",
        "",
        "## Observed WP categories/tags (top 40)",
        "",
        "| term | count |",
        "|---|---|",
    ]
    for term, count in results["wp_terms"].most_common(40):
        lines.append(f"| {term} | {count} |")

    lines += ["", "## Title keyword cues", "", "| cue | count | example records |", "|---|---|---|"]
    for cue, count in results["title_cues"].most_common():
        ex = "<br>".join(results["examples"].get(cue, [])[:2])
        lines.append(f"| {cue} | {count} | {ex} |")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT_PATH}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Taxonomy discovery evidence")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args(argv)
    if not args.input.exists():
        print(f"input missing: {args.input} — run project.normalize / project.dedupe first")
        return 1
    write_report(run(args.input), args.input)
    return 0


if __name__ == "__main__":
    sys.exit(main())
