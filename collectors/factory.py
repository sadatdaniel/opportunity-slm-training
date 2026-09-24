"""Collector factory: map a recipe's ``method`` to its implementation."""

from __future__ import annotations

from collectors.base import PoliteFetcher
from collectors.html_collector import HtmlCollector
from collectors.rss_collector import RssCollector
from collectors.wp_rest import WpRestCollector

COLLECTORS = {
    WpRestCollector.method: WpRestCollector,
    RssCollector.method: RssCollector,
    HtmlCollector.method: HtmlCollector,
}


def get_collector(method: str, fetcher: PoliteFetcher):
    try:
        return COLLECTORS[method](fetcher)
    except KeyError:
        raise ValueError(f"unknown collection method: {method!r}") from None
