"""Normalize the human-curated source list into a machine-readable registry.

The original list lives in ``100_academic_sources.md`` as a bare JSON array.
That file remains the provenance record; this module derives
``sources/registry.yaml`` from it deterministically (stable slugs, no
timestamps) so the output diffs cleanly in Git.

Usage::

    python -m project.sources.registry           # (re)generate registry.yaml
    python -m project.sources.registry --check   # exit 1 if out of date
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_SOURCES = PROJECT_ROOT / "100_academic_sources.md"
DEFAULT_REGISTRY = PROJECT_ROOT / "sources" / "registry.yaml"


def slugify(name: str) -> str:
    """Stable snake_case id from a source name (accents folded to ASCII)."""
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", folded.lower()).strip("_")
    return slug or "unnamed"


def domain_of(url: str) -> str:
    """Registrable host for a URL, with leading ``www.`` stripped."""
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def load_raw_sources(path: Path = DEFAULT_RAW_SOURCES) -> list[dict]:
    """Read the original JSON-array source list."""
    return json.loads(path.read_text(encoding="utf-8").strip())


def build_registry(raw: list[dict], origin_file: str = DEFAULT_RAW_SOURCES.name) -> list[dict]:
    registry: list[dict] = []
    used: set[str] = set()
    for entry in raw:
        name = entry["name"].strip()
        source_id = base = slugify(name)
        n = 2
        while source_id in used:  # distinct names can collide after slugifying
            source_id, n = f"{base}_{n}", n + 1
        used.add(source_id)
        postings_page = entry["postings_page"].strip()
        registry.append(
            {
                "source_id": source_id,
                "name": name,
                "domain": domain_of(postings_page),
                "scope": list(entry.get("scope", [])),
                "postings_page": postings_page,
                "api_endpoint": entry.get("api_endpoint", "").strip(),
                "origin_file": origin_file,
            }
        )
    return registry


def write_registry(registry: list[dict], path: Path = DEFAULT_REGISTRY) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Machine-readable source registry.\n"
        "# Generated from 100_academic_sources.md by project.sources.registry; do not hand-edit.\n"
        "# Edit the markdown source, then re-run: python -m project.sources.registry\n"
    )
    body = yaml.safe_dump(registry, sort_keys=False, allow_unicode=True, width=100)
    path.write_text(header + body, encoding="utf-8")


def load_registry(path: Path = DEFAULT_REGISTRY) -> list[dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate sources/registry.yaml")
    parser.add_argument("--check", action="store_true", help="exit 1 if the registry is out of date")
    args = parser.parse_args(argv)

    registry = build_registry(load_raw_sources())
    if args.check:
        if not DEFAULT_REGISTRY.exists():
            print("registry.yaml is missing")
            return 1
        current = yaml.safe_load(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        if current == registry:
            print("registry.yaml is up to date")
            return 0
        print("registry.yaml is out of date; re-run without --check")
        return 1

    write_registry(registry)
    print(f"wrote {len(registry)} sources to {DEFAULT_REGISTRY}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
