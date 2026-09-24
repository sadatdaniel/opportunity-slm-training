"""Fixture-based parser tests: no live network, httpx MockTransport only."""


import httpx
import pytest

from collectors.base import PoliteFetcher
from collectors.factory import get_collector
from collectors.html_collector import HtmlCollector
from collectors.records import html_to_text
from collectors.rss_collector import RssCollector
from collectors.wp_rest import WpRestCollector


def wp_post(post_id, slug, deadline=None):
    return {
        "id": post_id,
        "date": "2026-09-01T10:00:00",
        "date_gmt": "2026-09-01T10:00:00",
        "modified": "2026-09-02T09:00:00",
        "link": f"https://example.test/opps/{slug}/",
        "title": {"rendered": f"Opportunity {post_id} &amp; more"},
        "content": {"rendered": "<h2>Eligibility</h2><p>Open to students <b>under 30</b>.</p><ul><li>Requirement A</li><li>Requirement B</li></ul>"},
        "excerpt": {"rendered": "<p>Short blurb</p>"},
        "deadline": deadline,
        "_embedded": {
            "wp:term": [
                [
                    {"taxonomy": "category", "id": 5, "name": "Scholarships", "slug": "scholarships"},
                    {"taxonomy": "category", "id": 9, "name": "Competitions", "slug": "competitions"},
                ],
                [{"taxonomy": "post_tag", "id": 3, "name": "africa", "slug": "africa"}],
            ]
        },
    }


def wp_transport(pages):
    """Handler keyed on the URL string (parse_qs proved unreliable here)."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, text="")
        url = str(request.url)
        for page_key, posts in pages.items():
            if f"page={page_key}&" in url or url.endswith(f"page={page_key}"):
                resp = httpx.Response(200, json=posts)
                if posts:
                    resp.headers["X-WP-TotalPages"] = str(max(pages))
                return resp
        return httpx.Response(200, json=[])

    return handler


def test_wp_rest_collector_parses_and_paginates(tmp_path):
    pages = {1: [wp_post(1, "opp-1", deadline="2026-12-01"), wp_post(2, "opp-2")], 2: []}
    fetcher = PoliteFetcher(tmp_path / "cache", transport=httpx.MockTransport(wp_transport(pages)), respect_robots=True)
    recipe = {"source_id": "test", "source_name": "Test", "api_endpoint": "https://example.test/wp-json/wp/v2/posts"}
    records = list(WpRestCollector(fetcher).collect(recipe))

    assert len(records) == 2
    first = records[0]
    assert first["canonical_url"] == "https://example.test/opps/opp-1/"
    assert first["title"] == "Opportunity 1 & more"
    assert first["deadline"] == "2026-12-01"
    assert first["extra"]["wp_categories"] == ["Competitions", "Scholarships"]
    assert "Eligibility" in first["clean_text"]
    assert "<h2>" not in first["clean_text"]
    assert first["raw_text"].startswith("<h2>")
    assert first["record_id"] and first["content_hash"]


def test_html_to_text_preserves_structure():
    text = html_to_text(wp_post(1, "x")["content"]["rendered"])
    lines = text.splitlines()
    assert "Eligibility" in lines
    assert "Requirement A" in lines and "Requirement B" in lines


RSS_XML = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<title>Test Feed</title>
<item><title>Fellowship open</title><link>https://example.test/fellowship/</link>
<pubDate>Mon, 01 Sep 2026 10:00:00 +0000</pubDate>
<description><![CDATA[<p>Summary only</p>]]></description></item>
<item><title>Second</title><link>https://example.test/second/</link></item>
</channel></rss>"""


def test_rss_collector(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("feed"):
            return httpx.Response(200, text=RSS_XML)
        return httpx.Response(404)

    fetcher = PoliteFetcher(tmp_path / "cache", transport=httpx.MockTransport(handler), respect_robots=False)
    recipe = {"source_id": "test", "source_name": "Test", "feed_url": "https://example.test/feed", "max_records": 10}
    records = list(RssCollector(fetcher).collect(recipe))

    assert [r["title"] for r in records] == ["Fellowship open", "Second"]
    assert records[0]["canonical_url"] == "https://example.test/fellowship/"
    assert records[0]["published_at"].startswith("2026-09-01")
    assert records[0]["extra"]["feed_title"] == "Test Feed"


LISTING_HTML = """
<html><body>
<article><h2><a href="/opp/a/">Opp A</a></h2></article>
<article><h2><a href="/opp/b/">Opp B</a></h2></article>
</body></html>"""

DETAIL_HTML = """
<html><body>
<div class="entry-content"><p>Body text</p><h3>Benefits</h3><ul><li>$5000</li></ul></div>
<span class="deadline">2026-11-30</span>
</body></html>"""


def test_html_collector_with_detail_pages(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/robots.txt":
            return httpx.Response(404, text="")
        if path.startswith("/opp/"):
            return httpx.Response(200, text=DETAIL_HTML)
        if path == "/listings" or path == "/listings/":
            return httpx.Response(200, text=LISTING_HTML)
        return httpx.Response(404)

    fetcher = PoliteFetcher(tmp_path / "cache", transport=httpx.MockTransport(handler), respect_robots=False)
    recipe = {
        "source_id": "test",
        "source_name": "Test",
        "listing_url": "https://example.test/listings",
        "item_selector": "article",
        "title_selector": "h2 a",
        "detail": {"content_selector": "div.entry-content", "deadline_selector": "span.deadline"},
        "max_records": 10,
    }
    records = list(HtmlCollector(fetcher).collect(recipe))

    assert len(records) == 2
    assert records[0]["canonical_url"] == "https://example.test/opp/a/"
    assert records[0]["deadline"] == "2026-11-30"
    assert "Body text" in records[0]["clean_text"]
    assert "$5000" in records[0]["clean_text"]


def test_factory_unknown_method():
    with pytest.raises(ValueError):
        get_collector("nope", None)


def test_record_id_stable_across_calls():
    from collectors.records import stable_record_id

    assert stable_record_id("https://x.test/a") == stable_record_id("https://x.test/a")
    assert stable_record_id("https://x.test/a") != stable_record_id("https://x.test/b")
