"""Generic recipe-driven HTML collector for server-rendered listing pages.

Used only where no API or feed exists (brief section 8 preference order).
Recipes supply CSS selectors; keep them honest and tested with fixtures.
"""

from __future__ import annotations

from collections.abc import Iterator
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from collectors.base import PoliteFetcher
from collectors.records import html_to_text, make_record


class HtmlCollector:
    method = "html"

    def __init__(self, fetcher: PoliteFetcher):
        self.fetcher = fetcher

    def collect(self, recipe: dict) -> Iterator[dict]:
        listing = recipe["listing_url"]
        pagination = recipe.get("pagination", {})
        max_pages = int(pagination.get("max_pages", 1))
        max_records = int(recipe.get("max_records", 100))

        seen = 0
        for page_number in range(pagination.get("start", 1), max_pages + 1):
            url = self._page_url(listing, pagination, page_number)
            try:
                result = self.fetcher.get(url)
            except Exception:  # noqa: BLE001 - skip dead pages, keep collecting
                continue
            soup = BeautifulSoup(result.text, "lxml")

            items = soup.select(recipe["item_selector"])
            if not items:
                break
            for item in items:
                if seen >= max_records:
                    return
                record = self._item_record(item, recipe, url)
                if record is not None:
                    yield record
                    seen += 1

    def _page_url(self, listing: str, pagination: dict, page_number: int) -> str:
        template = pagination.get("path_template")  # e.g. "/page/{page}"
        if template:
            return listing.rstrip("/") + template.format(page=page_number)
        if page_number <= 1:
            return listing
        sep = "&" if "?" in listing else "?"
        return f"{listing}{sep}{pagination.get('page_param', 'page')}={page_number}"

    def _item_record(self, item, recipe: dict, listing_url: str) -> dict | None:
        title_node = item.select_one(recipe["title_selector"])
        link_node = item.select_one(recipe.get("link_selector", "a[href]"))
        if title_node is None and link_node is None:
            return None
        title = title_node.get_text(" ", strip=True) if title_node else link_node.get_text(" ", strip=True)
        href = urljoin(listing_url, link_node["href"]) if link_node and link_node.has_attr("href") else listing_url

        raw_html, clean_text, deadline = "", "", None
        if recipe.get("detail", {}).get("content_selector") and href:
            try:
                page = self.fetcher.get(href)
            except Exception:  # noqa: BLE001
                page = None
            if page is not None:
                soup = BeautifulSoup(page.text, "lxml")
                content = soup.select_one(recipe["detail"]["content_selector"])
                if content:
                    for tag in content(["script", "style", "nav", "footer", "aside"]):
                        tag.decompose()
                    raw_html = str(content)
                    clean_text = html_to_text(raw_html)
                if recipe["detail"].get("deadline_selector"):
                    node = soup.select_one(recipe["detail"]["deadline_selector"])
                    if node:
                        deadline = node.get_text(" ", strip=True)

        return make_record(
            source_id=recipe["source_id"],
            source_name=recipe.get("source_name", recipe["source_id"]),
            source_url=recipe.get("postings_page", ""),
            listing_url=listing_url,
            canonical_url=href,
            title=title,
            raw_text=raw_html or title,
            clean_text=clean_text or None,
            deadline=deadline,
        )
