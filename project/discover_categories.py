"""Discover WP category IDs for targeted collection (brief sections 8-9, 39A step 8).

Generic slugs don't match sites' own taxonomies, so for each WP source this
searches its /wp-json/wp/v2/categories endpoint per target keyword and
persists the discovered IDs into the recipe as ``target_category_ids`` —
the reusable artifact, so the discovery never has to run again.

Usage::

    python -m project.discover_categories                # all WP sources
    python -m project.discover_categories --sources opportunity_desk,ofy
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx
import yaml

from project.freeze_corpus import PROJECT_ROOT
from project.teachers import load_env

RECIPES_DIR = PROJECT_ROOT / "recipes"
TARGET_KEYWORDS = ["postdoc", "postdoctoral", "exchange", "summer school", "grant", "award", "fellowship"]
FOLLOW = httpx.Client(timeout=30, follow_redirects=True)


def discover_for_source(api_endpoint: str, keywords: list[str]) -> dict[str, list[int]]:
    base = api_endpoint.split("/wp-json/")[0]
    found: dict[str, list[int]] = {}
    for keyword in keywords:
        try:
            r = FOLLOW.get(
                f"{base}/wp-json/wp/v2/categories",
                params={"search": keyword, "per_page": 5},
            )
        except httpx.HTTPError:
            continue
        if r.status_code != 200:
            continue
        ids = [c["id"] for c in r.json() if isinstance(c, dict) and c.get("id")]
        if ids:
            found[keyword] = ids
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Discover WP category IDs for weak-class collection")
    parser.add_argument("--sources", help="comma list of source_ids (default: all wp_rest recipes)")
    parser.add_argument("--keywords", nargs="*", default=TARGET_KEYWORDS)
    args = parser.parse_args(argv)
    load_env()

    updated = 0
    for recipe_path in sorted(RECIPES_DIR.glob("*.yaml")):
        recipe = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
        if recipe.get("method") != "wp_rest":
            continue
        if args.sources and recipe["source_id"] not in args.sources.split(","):
            continue
        found = discover_for_source(recipe["api_endpoint"], args.keywords)
        if found:
            recipe["target_category_ids"] = found
            recipe_path.write_text(
                yaml.safe_dump(recipe, sort_keys=False, allow_unicode=True), encoding="utf-8"
            )
            total = sum(len(v) for v in found.values())
            print(f"{recipe['source_id']}: {total} category ids for {list(found)}", flush=True)
            updated += 1
    print(f"updated {updated} recipes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
