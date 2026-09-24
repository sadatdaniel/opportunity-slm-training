import httpx
import pytest

from collectors.base import FetchRefused, PoliteFetcher


def make_fetcher(handler, tmp_path, **kwargs):
    return PoliteFetcher(tmp_path / "cache", transport=httpx.MockTransport(handler), **kwargs)


def test_get_caches_response(tmp_path):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, text="hello")

    fetcher = make_fetcher(handler, tmp_path, respect_robots=False)
    first = fetcher.get("https://example.test/post/1")
    second = fetcher.get("https://example.test/post/1")

    assert first.text == "hello" and not first.from_cache
    assert second.from_cache and second.text == "hello"
    assert calls["n"] == 1, "second GET must come from cache"


def test_robots_disallow_refuses(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private/\n")
        return httpx.Response(200, text="page")

    fetcher = make_fetcher(handler, tmp_path)
    with pytest.raises(FetchRefused):
        fetcher.get("https://example.test/private/listing")


def test_403_marks_refused(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, text="not found")
        return httpx.Response(403, text="forbidden")

    fetcher = make_fetcher(handler, tmp_path)
    with pytest.raises(FetchRefused):
        fetcher.get("https://example.test/feed")
    assert fetcher._hosts["example.test"].refused


def test_robots_403_is_treated_as_refusal(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(403, text="no bots")
        return httpx.Response(200, text="page")

    fetcher = make_fetcher(handler, tmp_path)
    with pytest.raises(FetchRefused):
        fetcher.get("https://example.test/anything")
