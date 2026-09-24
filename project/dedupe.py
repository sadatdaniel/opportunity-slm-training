"""Layered deduplication (build brief section 14).

The same opportunity appears on organizer sites, aggregators, and copied
announcements. This builds duplicate GROUPS (evidence preserved) rather than
silently dropping rows, using:

  layer 1: exact content hash
  layer 2: normalized-title near-match within title-length buckets
           (RapidFuzz-free: difflib ratio on normalized titles)

Each group gets a preferred canonical record (most complete text, then
earliest publication). Union-find keeps grouping transitive.

Usage::

    python -m project.dedupe
"""

from __future__ import annotations

import difflib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NORMALIZED_PATH = PROJECT_ROOT / "data" / "normalized" / "records.jsonl"
DEDUPED_PATH = PROJECT_ROOT / "data" / "normalized" / "deduped.jsonl"
GROUPS_PATH = PROJECT_ROOT / "data" / "manifests" / "duplicate_groups.json"
REPORT_PATH = PROJECT_ROOT / "reports" / "dedup_report.md"

SIMILARITY_THRESHOLD = 0.90


def normalize_title(title: str) -> str:
    title = title.lower()
    title = re.sub(r"[^a-z0-9 ]+", " ", title)
    title = re.sub(r"\b(scholarship|scholarships|application|apply|now|open|2026|2025|fully funded)\b", " ", title)
    return re.sub(r"\s+", " ", title).strip()


def word_count(text: str) -> int:
    return len(text.split())


class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def find_duplicate_groups(records: list[dict]) -> list[list[int]]:
    n = len(records)
    uf = UnionFind(n)

    # Layer 1: exact content hash
    by_hash: dict[str, int] = {}
    for i, rec in enumerate(records):
        h = rec["content_hash"]
        if h in by_hash:
            uf.union(by_hash[h], i)
        else:
            by_hash[h] = i

    # Layer 2: near-duplicate titles, blocked by first word + length bucket
    titles = [(i, normalize_title(rec["title"])) for i, rec in enumerate(records)]
    buckets: dict[tuple, list[int]] = defaultdict(list)
    for i, t in titles:
        if not t:
            continue
        first_word = t.split()[0][:12]
        bucket = len(t) // 10
        buckets[(first_word, bucket)].append(i)
    for members in buckets.values():
        for a in range(len(members)):
            for b in range(a + 1, len(members)):
                ia, ib = members[a], members[b]
                ta, tb = titles[ia][1], titles[ib][1]
                if not ta or not tb:
                    continue
                if abs(len(ta) - len(tb)) > max(len(ta), len(tb)) * 0.4:
                    continue
                if difflib.SequenceMatcher(None, ta, tb).ratio() >= SIMILARITY_THRESHOLD:
                    uf.union(ia, ib)

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[uf.find(i)].append(i)
    return list(groups.values())


def prefer_canonical(group: list[int], records: list[dict]) -> int:
    """Most complete record wins; tie-break on earliest publication."""
    def key(i: int) -> tuple:
        rec = records[i]
        recency = rec.get("published_at") or "9999-12-31"
        return (-word_count(rec.get("clean_text") or ""), recency)

    return min(group, key=key)


def run_dedupe() -> dict:
    records = [
        json.loads(line)
        for line in NORMALIZED_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    groups = find_duplicate_groups(records)

    DEDUPED_PATH.parent.mkdir(parents=True, exist_ok=True)
    canonical_ids: set[str] = set()
    with DEDUPED_PATH.open("w", encoding="utf-8") as out:
        for group in groups:
            keep = prefer_canonical(group, records)
            rec = records[keep]
            canonical_ids.add(rec["record_id"])
            rec = dict(rec)
            rec["duplicate_group_size"] = len(group)
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Group evidence for review tooling and cross-split leakage prevention.
    group_details = []
    for group in groups:
        keep = prefer_canonical(group, records)
        group_details.append(
            {
                "canonical_record_id": records[keep]["record_id"],
                "size": len(group),
                "members": [
                    {
                        "record_id": records[i]["record_id"],
                        "source_id": records[i]["source_id"],
                        "title": records[i]["title"][:120],
                        "canonical_url": records[i]["canonical_url"],
                        "is_canonical": i == keep,
                    }
                    for i in group
                ],
            }
        )
    GROUPS_PATH.parent.mkdir(parents=True, exist_ok=True)
    GROUPS_PATH.write_text(json.dumps(group_details, ensure_ascii=False, indent=1), encoding="utf-8")

    sizes = Counter(len(g) for g in groups)
    cross_source = sum(
        1 for g in groups if len({records[i]["source_id"] for i in g}) > 1
    )
    return {
        "input": len(records),
        "groups": len(groups),
        "canonical": len(canonical_ids),
        "duplicates_removed": len(records) - len(canonical_ids),
        "cross_source_groups": cross_source,
        "size_histogram": {str(k): v for k, v in sorted(sizes.items())},
    }


def write_report(results: dict) -> None:
    lines = [
        "# Deduplication Report",
        "",
        f"- input records: {results['input']}",
        f"- duplicate groups: {results['groups']}",
        f"- canonical records kept: {results['canonical']}",
        f"- duplicates removed: {results['duplicates_removed']}",
        f"- groups spanning multiple sources: {results['cross_source_groups']}",
        "",
        "## Group size histogram",
        "",
    ]
    for size, count in results["size_histogram"].items():
        lines.append(f"- groups of size {size}: {count}")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    results = run_dedupe()
    write_report(results)
    print(json.dumps(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
