"""Source inventory probe (build brief section 8).

Before collecting anything, probe every registered source to learn how it can
be collected: public API availability (with post totals for WP REST), RSS/Atom
feeds, robots.txt stance toward the postings page, and server- vs
JS-rendered heuristics. Results are written incrementally to
``data/inventory.json`` (crash-safe, cached responses make re-runs free) and
summarized in ``reports/source_inventory.md``.

Usage::

    python -m project.sources.inventory            # probe unprobed sources
    python -m project.sources.inventory --force    # re-probe everything
    python -m project.sources.inventory --source euraxess
    python -m project.sources.inventory --report   # rebuild report only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import feedparser
from bs4 import BeautifulSoup

from collectors.base import FetchRefused, PoliteFetcher
from project.sources.registry import DEFAULT_REGISTRY, load_registry

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = PROJECT_ROOT / "data" / "inventory.json"
REPORT_PATH = PROJECT_ROOT / "reports" / "source_inventory.md"

SPA_MARKERS = ["__NEXT_DATA__", 'id="root"', 'id="app"', "ng-app", "data-reactroot", "nuxt"]
WP_PATTERN = re.compile(r"wp-json|wp-content|wp-includes")

INVENTORY_LOCK = threading.Lock()


def load_inventory() -> dict:
    if INVENTORY_PATH.exists():
        return json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    return {}


def save_inventory(inventory: dict) -> None:
    INVENTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    INVENTORY_PATH.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )


def probe_api(fetcher: PoliteFetcher, source: dict) -> dict:
    """Probe the declared API endpoint. For WP REST, request a single post."""
    api_url = source["api_endpoint"]
    if not api_url:
        return {"kind": "none", "error": "no api_endpoint declared"}
    params = {"per_page": "1"} if "/wp-json/" in api_url else None
    try:
        result = fetcher.get(api_url, params=params)
    except FetchRefused as exc:
        return {"kind": "refused", "error": str(exc)}
    except Exception as exc:  # noqa: BLE001 - record and continue
        return {"kind": "error", "error": str(exc)[:300]}

    record = {"status": result.status, "final_url": result.final_url}
    text = result.text.strip()
    if text.startswith(("{", "[")):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return {**record, "kind": "html"}
        if isinstance(payload, list):
            if "/wp-json/" in api_url:
                first = payload[0] if payload else {}
                record.update(
                    kind="wp_rest",
                    has_posts=bool(payload),
                    sample_fields=sorted(first.keys())[:25] if isinstance(first, dict) else [],
                )
            else:
                record.update(kind="json_list", items=len(payload))
            return record
        if isinstance(payload, dict):
            record["kind"] = "wp_rest" if "/wp-json/" in api_url else "json_object"
            return record
    return {**record, "kind": "html"}


def probe_rss(fetcher: PoliteFetcher, source: dict, is_wp: bool) -> dict:
    candidates = []
    base = source["postings_page"].rstrip("/")
    if is_wp:
        candidates.append(f"{base}/feed")
    else:
        candidates += [f"{base}/feed", f"{base}/rss", f"{base}/rss.xml", f"{base}/atom.xml"]
    for url in candidates[:2]:  # cap probes per source
        try:
            result = fetcher.get(url)
        except Exception:  # noqa: BLE001
            continue
        parsed = feedparser.parse(result.text)
        if parsed.entries or parsed.feed.get("title"):
            return {
                "url": url,
                "kind": "rss" if "rss" in (parsed.version or "") else "atom",
                "title": parsed.feed.get("title", ""),
                "entries_on_first_page": len(parsed.entries),
                "status": result.status,
            }
    return {"error": "no feed found"}


def probe_page(fetcher: PoliteFetcher, source: dict) -> dict:
    try:
        result = fetcher.get(source["postings_page"])
    except FetchRefused as exc:
        return {"status": 403, "refused": True, "error": str(exc)[:200]}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)[:300]}

    html = result.text
    soup = BeautifulSoup(html, "lxml")
    markers = [m for m in SPA_MARKERS if m in html]
    return {
        "status": result.status,
        "final_url": result.final_url,
        "html_bytes": len(html.encode("utf-8", "ignore")),
        "article_tags": len(soup.find_all("article")),
        "links": len(soup.find_all("a")),
        "looks_like_wordpress": bool(WP_PATTERN.search(html)),
        "spa_markers": markers,
        "server_rendered_guess": len(html) > 15000
        and (len(soup.find_all("a")) > 20)
        and not markers,
    }


def probe_robots(fetcher: PoliteFetcher, source: dict) -> dict:
    try:
        allowed = fetcher.robots_allows(source["postings_page"])
        return {"postings_page_allowed": allowed}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)[:200]}


def recommended_method(probe: dict) -> str:
    api, rss, page = probe["api"], probe["rss"], probe["page"]
    # "blocked" means the documents themselves are inaccessible. An API path
    # disallowed by robots does not block the HTML route (e.g. EURAXESS).
    page_blocked = page.get("refused") or probe["robots"].get("postings_page_allowed") is False
    if page_blocked:
        return "blocked_document"
    if api.get("kind") == "wp_rest":
        return "wp_rest"
    if api.get("kind") in ("json_list", "json_object"):
        return "api_json"
    if rss.get("url"):
        return "rss"
    if page.get("status") == 200 and page.get("html_bytes", 0) > 10000:
        return "html"
    return "needs_manual_review"

def probe_source(fetcher: PoliteFetcher, source: dict) -> dict:
    api = probe_api(fetcher, source)
    is_wp = api.get("kind") == "wp_rest" or "/wp-json/" in source["api_endpoint"]
    rss = probe_rss(fetcher, source, is_wp)
    page = probe_page(fetcher, source)
    robots = probe_robots(fetcher, source)
    probe = {"api": api, "rss": rss, "page": page, "robots": robots}
    probe["recommended_method"] = recommended_method(probe)
    return probe


def write_report(inventory: dict, registry: dict[str, dict]) -> None:
    methods = Counter(rec["probe"]["recommended_method"] for rec in inventory.values())
    scope_counts = Counter()
    for source in registry.values():
        scope_counts.update(source["scope"])

    lines = [
        "# Source Inventory",
        "",
        f"Probed {len(inventory)} of {len(registry)} registered sources. "
        "Machine-readable results: `data/inventory.json`.",
        "",
        "## Recommended collection methods",
        "",
        "| method | sources |",
        "|---|---|",
    ]
    for method, count in methods.most_common():
        lines.append(f"| {method} | {count} |")

    lines += ["", "## Per-source results", "",
              "| source | domain | method | API | posts | feed | robots | notes |",
              "|---|---|---|---|---|---|---|---|"]
    for source_id in sorted(inventory):
        rec = inventory[source_id]
        probe = rec["probe"]
        api, rss, page, robots = probe["api"], probe["rss"], probe["page"], probe["robots"]
        api_cell = f'{api.get("kind", "?")}/{api.get("status", "-")}'
        posts_cell = "yes" if api.get("has_posts") else "-"
        feed_cell = rss.get("kind", "-") if rss.get("url") else "-"
        robots_cell = str(robots.get("postings_page_allowed", "?")).lower()
        notes = []
        if page.get("spa_markers"):
            notes.append("JS-rendered:" + ",".join(page["spa_markers"][:2]))
        if page.get("refused"):
            notes.append("403")
        for key in ("error",):
            if api.get(key):
                notes.append("api:" + str(api[key])[:60])
        lines.append(
            f"| {source_id} | {rec['domain']} | {probe['recommended_method']} | {api_cell} "
            f"| {posts_cell} | {feed_cell} | {robots_cell} | {'; '.join(notes)[:80]} |"
        )

    lines += ["", "## Raw source scope frequency (taxonomy discovery input)", ""]
    for scope, count in scope_counts.most_common():
        lines.append(f"- {scope}: {count}")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"report written to {REPORT_PATH}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe all registered sources")
    parser.add_argument("--force", action="store_true", help="re-probe even if results exist")
    parser.add_argument("--source", help="probe a single source_id")
    parser.add_argument("--report", action="store_true", help="only rebuild the markdown report")
    parser.add_argument("--workers", type=int, default=4, help="probing threads")
    args = parser.parse_args(argv)

    registry = {s["source_id"]: s for s in load_registry(DEFAULT_REGISTRY)}
    inventory = load_inventory()

    if args.report:
        write_report(inventory, registry)
        return 0

    if args.source:
        targets = [registry[args.source]]
    else:
        targets = [s for s in registry.values() if args.force or s["source_id"] not in inventory]

    fetcher = PoliteFetcher(PROJECT_ROOT / "data" / "cache")
    print(f"probing {len(targets)} sources ({len(inventory)} already probed)")

    def run(source: dict) -> None:
        try:
            probe = probe_source(fetcher, source)
        except Exception as exc:  # noqa: BLE001 - never lose the whole run
            probe = {"recommended_method": "needs_manual_review", "fatal": str(exc)[:300]}
        record = {
            "source_id": source["source_id"],
            "name": source["name"],
            "domain": source["domain"],
            "scope": source["scope"],
            "probe": probe,
        }
        with INVENTORY_LOCK:
            inventory[source["source_id"]] = record
            save_inventory(inventory)
        print(f"  {source['source_id']}: {probe['recommended_method']}", flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(run, targets))

    fetcher.close()
    write_report(inventory, registry)
    return 0


if __name__ == "__main__":
    sys.exit(main())
