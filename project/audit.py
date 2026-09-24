"""Taxonomy audit sample and imbalance report (v2 brief, 39A steps 3-4).

Labels do not exist yet, so stratification uses WEAK signals (WP site
categories/tags plus title keywords) purely to assemble a human-reviewable
sample of 10-15 records per taxonomy-v1 category, with extra depth for the
known overlap-prone categories. The sample file is what a human audits to
answer: "can people apply taxonomy v1 consistently?"

Also writes the category/source imbalance report that later steers collection.

Usage::

    python -m project.audit
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict

import yaml

from project.freeze_corpus import PROJECT_ROOT

DEDUPED_PATH = PROJECT_ROOT / "data" / "normalized" / "deduped.jsonl"
TAXONOMY_CONFIG = PROJECT_ROOT / "config" / "taxonomy_v1.yaml"
SAMPLE_REPORT = PROJECT_ROOT / "reports" / "taxonomy_audit_sample.md"
IMBALANCE_REPORT = PROJECT_ROOT / "reports" / "imbalance_report.md"

SAMPLE_PER_CATEGORY = 12
# brief step 3: extra attention to overlap-prone categories
OVERSAMPLE = {"fellowships": 20, "phd": 20, "postdoc": 20, "grants": 20, "awards": 20, "competitions": 20}

# Weak-signal keyword -> candidate category. Matches on title only.
CANDIDATE_SIGNALS = {
    "scholarships": ["scholarship", "bursary", "stipend"],
    "fellowships": ["fellowship"],
    "phd": ["phd", "doctoral"],
    "postdoc": ["postdoc", "postdoctoral"],
    "grants": ["grant"],
    "internships": ["internship"],
    "competitions": ["competition", "challenge", "hackathon"],
    "awards": ["award", "prize"],
    "conferences": ["conference", "summit", "symposium"],
    "workshops": ["workshop", "summer school", "training"],
    "exchange_programs": ["exchange"],
}


def candidates_by_category(records: list[dict]) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        title = rec["title"].lower()
        for category, keywords in CANDIDATE_SIGNALS.items():
            if any(kw in title for kw in keywords):
                buckets[category].append(rec)
                break  # first match wins; overlap noise is what the audit is for
    return buckets


def write_sample(buckets: dict[str, list[dict]], categories: list[str]) -> None:
    lines = [
        "# Taxonomy v1 Audit Sample (human review)",
        "",
        "Stratified by WEAK signals (title keywords) — not labels. For each record,",
        "decide: does it belong to the suggested category, a neighboring one, or is",
        "it genuinely ambiguous? Note any definition that fails.",
        "",
        "Overlap-prone categories are oversampled (20 records).",
    ]
    for category in categories:
        wanted = OVERSAMPLE.get(category, SAMPLE_PER_CATEGORY)
        candidates = buckets.get(category, [])
        if not candidates:
            lines += [f"\n## {category} — NO TITLE SIGNALS FOUND (expect weak corpus coverage)", ""]
            continue
        lines += [f"\n## {category} ({len(candidates)} candidates, showing {min(wanted, len(candidates))})", ""]
        for rec in candidates[:wanted]:
            lines.append(f"- [{rec['source_id']}] {rec['title'][:110]}")
            lines.append(f"  {rec['canonical_url']}")
    SAMPLE_REPORT.parent.mkdir(parents=True, exist_ok=True)
    SAMPLE_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {SAMPLE_REPORT}")


def write_imbalance(buckets: dict[str, list[dict]], records: list[dict], categories: list[str]) -> None:
    by_source = Counter(r["source_id"] for r in records)
    signal_counts = {c: len(buckets.get(c, [])) for c in categories}
    no_signal = len(records) - sum(signal_counts.values())
    total = len(records)

    lines = [
        "# Category / Source Imbalance Report",
        "",
        f"Corpus v1: {total} canonical records from {len(by_source)} sources.",
        "Category figures use weak title signals only (labels come from the teacher pilot)",
        "and lower-bound true coverage; they identify clearly starved classes.",
        "",
        "## Signal-based category coverage",
        "",
        "| category | candidates | share of corpus |",
        "|---|---|---|",
    ]
    for category in sorted(signal_counts, key=lambda c: -signal_counts[c]):
        share = signal_counts[category] / total
        lines.append(f"| {category} | {signal_counts[category]} | {share:.1%} |")
    lines.append(f"| (no type signal in title) | {no_signal} | {no_signal / total:.1%} |")

    lines += [
        "",
        "## Source distribution",
        "",
        "| source | records | share |",
        "|---|---|---|",
    ]
    for source, count in by_source.most_common():
        lines.append(f"| {source} | {count} | {count / total:.1%} |")

    lines += [
        "",
        "## Collection guidance (model-driven, brief step 8)",
        "",
    ]
    starved = [c for c, n in signal_counts.items() if n < total * 0.02]
    if starved:
        lines.append(f"- Likely underrepresented: {', '.join(sorted(starved))} — preferential collection once measured.")
    top_share = max(by_source.values()) / total
    lines.append(
        f"- Largest source holds {top_share:.0%} of the corpus; source-aware splits and"
        " the unseen-source holdout (already in build_dataset) guard against overfitting it."
    )
    IMBALANCE_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {IMBALANCE_REPORT}")


def main(argv: list[str] | None = None) -> int:
    taxonomy = yaml.safe_load(TAXONOMY_CONFIG.read_text(encoding="utf-8"))
    categories = taxonomy["categories"]
    records = [
        json.loads(line)
        for line in DEDUPED_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    buckets = candidates_by_category(records)
    write_sample(buckets, categories)
    write_imbalance(buckets, records, categories)
    return 0


if __name__ == "__main__":
    sys.exit(main())
