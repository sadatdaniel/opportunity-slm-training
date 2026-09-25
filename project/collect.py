"""Collect opportunities from registered sources into ``data/raw/``.

Usage::

    python -m project.collect --source youth_opportunities
    python -m project.collect --source youth_opportunities --limit 50
    python -m project.collect --all --methods wp_rest,rss

Recipes live in ``recipes/<source_id>.yaml``. When one is missing it is
provisioned automatically from the source inventory's recommended method (WP
REST and RSS only; HTML sources need hand-written selectors) and written to
disk so it stays inspectable, tunable, and reusable (brief section 9).

Raw records append to ``data/raw/<source_id>/batch_<timestamp>.jsonl`` with
full provenance. Per-run stats land in
``data/manifests/collection_log.yaml``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

from collectors.base import PoliteFetcher
from collectors.factory import get_collector
from project.sources.registry import DEFAULT_REGISTRY, load_registry

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RECIPES_DIR = PROJECT_ROOT / "recipes"
RAW_DIR = PROJECT_ROOT / "data" / "raw"
LOG_PATH = PROJECT_ROOT / "data" / "manifests" / "collection_log.yaml"
INVENTORY_PATH = PROJECT_ROOT / "data" / "inventory.json"

# Adaptive default quotas (brief section 11): easy structured APIs get more.
DEFAULT_QUOTA = {"wp_rest": 250, "rss": 120}


def load_inventory() -> dict:
    if INVENTORY_PATH.exists():
        return json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    return {}


def recommended_method(source: dict, inventory: dict) -> str:
    probe = inventory.get(source["source_id"], {}).get("probe")
    if probe:
        return probe["recommended_method"]
    return "wp_rest" if "/wp-json/" in source["api_endpoint"] else "needs_manual_review"


def provision_recipe(source: dict, method: str, inventory: dict) -> dict | None:
    """Create an initial recipe for API/feed sources; HTML needs humans."""
    recipe = {
        "source_id": source["source_id"],
        "source_name": source["name"],
        "postings_page": source["postings_page"],
        "method": method,
        "parser_version": 1,
        "last_tested": datetime.now(UTC).date().isoformat(),
        "notes": "auto-provisioned from source inventory; hand-tune as needed",
    }
    if method == "wp_rest":
        recipe.update(
            api_endpoint=source["api_endpoint"],
            per_page=50,
            max_records=DEFAULT_QUOTA["wp_rest"],
            embed_terms=True,
            deadline_fields=["deadline", "application_deadline", "deadline_date"],
        )
    elif method == "rss":
        feed_url = (
            inventory.get(source["source_id"], {}).get("probe", {}).get("rss", {}).get("url")
        )
        if not feed_url:
            feed_url = source["postings_page"].rstrip("/") + "/feed"
        recipe.update(feed_url=feed_url, max_records=DEFAULT_QUOTA["rss"])
    else:
        return None
    return recipe


def load_or_provision_recipe(source: dict, inventory: dict, force_method: str | None = None) -> tuple[dict | None, bool]:
    """Returns (recipe, provisioned)."""
    path = RECIPES_DIR / f"{source['source_id']}.yaml"
    if path.exists():
        return yaml.safe_load(path.read_text(encoding="utf-8")), False
    method = force_method or recommended_method(source, inventory)
    recipe = provision_recipe(source, method, inventory)
    if recipe is None:
        return None, False
    RECIPES_DIR.mkdir(exist_ok=True)
    path.write_text(
        yaml.safe_dump(recipe, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return recipe, True


def existing_record_ids(source_id: str) -> set[str]:
    """Record ids already collected for this source (in-source dedup)."""
    ids: set[str] = set()
    for path in (RAW_DIR / source_id).glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    ids.add(json.loads(line)["record_id"])
                except (json.JSONDecodeError, KeyError):
                    continue
    return ids


def append_log(entry: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log = yaml.safe_load(LOG_PATH.read_text(encoding="utf-8")) if LOG_PATH.exists() else {"runs": []}
    log["runs"].append(entry)
    LOG_PATH.write_text(yaml.safe_dump(log, sort_keys=False, allow_unicode=True), encoding="utf-8")


def collect_source(source: dict, inventory: dict, limit: int | None, force_method: str | None,
                   targeted: str | None = None) -> dict:
    started = datetime.now(UTC)
    recipe, provisioned = load_or_provision_recipe(source, inventory, force_method)
    if recipe is None:
        return {"source_id": source["source_id"], "skipped": f"no recipe for method {recommended_method(source, inventory)!r}"}

    if limit:
        recipe["max_records"] = limit
    if targeted:
        # model-driven collection into weak classes (brief step 8): WP
        # category slugs injected at runtime; recipes stay untouched
        recipe["target_categories"] = [s.strip() for s in targeted.split(",") if s.strip()]
        recipe["per_slug"] = recipe.get("max_records", 250)

    fetcher = PoliteFetcher(PROJECT_ROOT / "data" / "cache")
    collector = get_collector(recipe["method"], fetcher)

    known_ids = existing_record_ids(source["source_id"])
    out_dir = RAW_DIR / source["source_id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"batch_{stamp}.jsonl"

    seen, new, errors = 0, 0, []
    with out_path.open("w", encoding="utf-8") as fh:
        try:
            for record in collector.collect(recipe):
                seen += 1
                if record["record_id"] in known_ids:
                    continue
                known_ids.add(record["record_id"])
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                new += 1
        except Exception as exc:  # noqa: BLE001 - keep partial results, log the failure
            errors.append(f"{type(exc).__name__}: {exc}"[:300])
            print(f"  error while collecting {source['source_id']}: {exc}", file=sys.stderr)

    fetcher.close()
    elapsed = (datetime.now(UTC) - started).total_seconds()
    entry = {
        "source_id": source["source_id"],
        "method": recipe["method"],
        "recipe_path": str(Path("recipes") / f"{source['source_id']}.yaml"),
        "batch_file": str(out_path.relative_to(PROJECT_ROOT)),
        "batch_sha256": hashlib.sha256(out_path.read_bytes()).hexdigest()
        if out_path.exists() and out_path.stat().st_size
        else None,
        "records_seen": seen,
        "records_new": new,
        "records_skipped_duplicate": seen - new,
        "recipe_provisioned": provisioned,
        "errors": errors[:5],
        "started_at": started.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "elapsed_seconds": round(elapsed, 1),
    }
    append_log(entry)
    return entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect raw opportunity records")
    parser.add_argument("--source", help="single source_id")
    parser.add_argument("--all", action="store_true", help="collect from every source with a viable method")
    parser.add_argument("--methods", help="comma list to restrict --all (e.g. wp_rest,rss)")
    parser.add_argument("--limit", type=int, help="override per-source max_records")
    parser.add_argument("--targeted", help="comma-separated WP category slugs to collect into weak classes")
    args = parser.parse_args(argv)

    registry = load_registry(DEFAULT_REGISTRY)
    inventory = load_inventory()
    methods = set(args.methods.split(",")) if args.methods else None

    if args.source:
        sources = [s for s in registry if s["source_id"] == args.source]
        if not sources:
            print(f"unknown source: {args.source}")
            return 1
    elif args.all:
        sources = registry
    else:
        parser.error("specify --source SOURCE_ID or --all")
        return 2

    for source in sources:
        method = force_method_check(source, inventory, methods) if methods else None
        if methods and method is None:
            print(f"skip {source['source_id']} (method not in {sorted(methods)})")
            continue
        result = collect_source(source, inventory, args.limit, method, args.targeted)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0


def force_method_check(source: dict, inventory: dict, methods: set[str]) -> str | None:
    """Method to force for this source if it is in the allowed set, else None."""
    recipe_path = RECIPES_DIR / f"{source['source_id']}.yaml"
    if recipe_path.exists():
        current = yaml.safe_load(recipe_path.read_text(encoding="utf-8")).get("method")
        return current if current in methods else None
    recommended = recommended_method(source, inventory)
    return recommended if recommended in methods else None


if __name__ == "__main__":
    sys.exit(main())
