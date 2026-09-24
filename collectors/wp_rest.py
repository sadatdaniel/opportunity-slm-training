"""WordPress REST API collector.

Most registry sources are WordPress sites exposing /wp-json/wp/v2/posts, which
gives full post content, dates, and often custom deadline fields without any
detail-page fetching. Embedded terms (categories/tags) are valuable taxonomy
clues for discovery (brief section 7), so recipes may enable ``embed_terms``.
"""

from __future__ import annotations

import json
from typing import Iterator

from collectors.base import FetchFailed, PoliteFetcher
from collectors.records import html_to_text, make_record


class WpRestCollector:
    method = "wp_rest"

    def __init__(self, fetcher: PoliteFetcher):
        self.fetcher = fetcher

    def collect(self, recipe: dict) -> Iterator[dict]:
        api = recipe["api_endpoint"]
        per_page = int(recipe.get("per_page", 50))  # WP hard maximum is 100
        max_records = int(recipe.get("max_records", 250))
        extra_params = dict(recipe.get("params", {}))
        if recipe.get("embed_terms", True):
            extra_params.setdefault("_embed", "wp:term")

        page, seen, total_pages = 1, 0, None
        yielded_ids: set[str] = set()
        while seen < max_records:
            params = {"per_page": str(per_page), "page": str(page), **extra_params}
            try:
                result = self.fetcher.get(api, params=params)
                posts = json.loads(result.text)
            except FetchFailed as exc:
                if exc.status == 400:  # WP signals "beyond last page" with 400
                    break
                raise
            if not isinstance(posts, list) or not posts:
                break
            if total_pages is None and result.headers.get("x-wp-totalpages"):
                total_pages = int(result.headers["x-wp-totalpages"])

            new_ids = {post.get("link", "") for post in posts} - yielded_ids
            if not new_ids:  # server started re-serving the same page: stop
                break

            for post in posts:
                record = self.to_record(post, recipe)
                if record["record_id"] in yielded_ids:
                    continue
                yielded_ids.add(record["record_id"])
                yield record
                seen += 1
                if seen >= max_records:
                    return

            if total_pages is not None and page >= total_pages:
                break
            page += 1

    def to_record(self, post: dict, recipe: dict) -> dict:
        content_html = (post.get("content") or {}).get("rendered", "")
        title = (post.get("title") or {}).get("rendered", "")
        published = post.get("date_gmt") or post.get("date")

        deadline = None
        for field in recipe.get("deadline_fields", ["deadline"]):
            value = post.get(field)
            if isinstance(value, str) and value.strip():
                deadline = value.strip()
                break

        categories, tags = [], []
        for term_group in (post.get("_embedded") or {}).get("wp:term", []):
            for term in term_group:
                name = (term.get("name") or "").strip()
                if not name:
                    continue
                if term.get("taxonomy") == "category":
                    categories.append(name)
                elif term.get("taxonomy") == "post_tag":
                    tags.append(name)

        return make_record(
            source_id=recipe["source_id"],
            source_name=recipe.get("source_name", recipe["source_id"]),
            source_url=recipe.get("postings_page", ""),
            listing_url=recipe["api_endpoint"],
            canonical_url=post.get("link", ""),
            title=title,
            raw_text=content_html,
            clean_text=html_to_text(content_html),
            published_at=published,
            deadline=deadline,
            extra={
                "wp_id": post.get("id"),
                "wp_modified": post.get("modified"),
                "wp_categories": sorted(set(categories)),
                "wp_tags": sorted(set(tags)),
                "excerpt": html_to_text((post.get("excerpt") or {}).get("rendered", ""))[:500],
            },
        )
