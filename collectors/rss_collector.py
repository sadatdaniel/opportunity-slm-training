"""RSS/Atom feed collector.

Feeds usually carry only summaries; when a recipe enables ``detail``, each
entry's link is fetched once and the main content extracted with the recipe's
detail selectors. Cached responses keep re-parsing free.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import feedparser
from bs4 import BeautifulSoup

from collectors.base import PoliteFetcher
from collectors.records import html_to_text, make_record


def _entry_html(entry) -> str:
    if entry.get("content"):
        return entry["content"][0].get("value", "")
    return entry.get("summary", "") or ""


def _entry_date(entry) -> str | None:
    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            return datetime(*parsed[:6], tzinfo=UTC).isoformat()
    return None


class RssCollector:
    method = "rss"

    def __init__(self, fetcher: PoliteFetcher):
        self.fetcher = fetcher

    def collect(self, recipe: dict) -> Iterator[dict]:
        feed_url = recipe["feed_url"]
        max_records = int(recipe.get("max_records", 120))
        result = self.fetcher.get(feed_url)
        parsed = feedparser.parse(result.text)

        yielded = 0
        for entry in parsed.entries:
            if yielded >= max_records:
                return
            link = entry.get("link", "")
            if not link:
                continue
            raw_html = _entry_html(entry)
            clean_text = html_to_text(raw_html)

            # Feeds carry summaries; fetch the detail page only when the feed
            # gave us too little to work with.
            if recipe.get("detail") and len(clean_text) < 1200:
                page = self._fetch_detail(link, recipe)
                if page:
                    raw_html, clean_text = page

            yield make_record(
                source_id=recipe["source_id"],
                source_name=recipe.get("source_name", recipe["source_id"]),
                source_url=recipe.get("postings_page", ""),
                listing_url=feed_url,
                canonical_url=link,
                title=entry.get("title", ""),
                raw_text=raw_html,
                clean_text=clean_text,
                published_at=_entry_date(entry),
                extra={"feed_title": parsed.feed.get("title", "")},
            )
            yielded += 1

    def _fetch_detail(self, url: str, recipe: dict) -> tuple[str, str] | None:
        detail = recipe.get("detail") or {}
        try:
            result = self.fetcher.get(url)
        except Exception:  # noqa: BLE001 - a dead detail page must not kill the run
            return None
        soup = BeautifulSoup(result.text, "lxml")
        node = soup.select_one(detail["content_selector"]) if detail.get("content_selector") else soup.body
        if node is None:
            return None
        for tag in node(["script", "style", "nav", "footer", "aside"]):
            tag.decompose()
        deadline = None
        if detail.get("deadline_selector"):
            dnode = soup.select_one(detail["deadline_selector"])
            if dnode:
                deadline = dnode.get_text(" ", strip=True)
        html = str(node)
        text = html_to_text(html)
        if deadline:
            text = f"DEADLINE: {deadline}\n\n{text}"
        return html, text
