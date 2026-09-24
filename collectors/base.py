"""Polite HTTP collection framework (see build brief sections 9-12).

Policy implemented here:
- one request per host at a time, conservative delay + jitter
- honor Retry-After; back off hard on 429/403/5xx and stop hammering refusers
- cache every successful response on disk so parser work never re-hits sites
- robots.txt checked before fetching; never bypass blocks, CAPTCHAs, or logins
- honest User-Agent identifying the research project
"""

from __future__ import annotations

import base64
import hashlib
import json
import random
import threading
import time
import urllib.robotparser
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

USER_AGENT = "opportunity-intelligence-research/0.1 (dataset build; polite; contact: repo owner)"

DEFAULT_DELAY = 2.0
DEFAULT_JITTER = 1.5
DEFAULT_TIMEOUT = 30.0

# Response headers kept alongside cached responses (lowercase).
KEPT_HEADERS = ["content-type", "x-wp-total", "x-wp-totalpages", "retry-after", "server"]


class FetchRefused(Exception):
    """The host actively refused automated access (403/robots-deny)."""


class FetchFailed(Exception):
    """Request failed after polite retries (network error or persistent 4xx/5xx)."""

    def __init__(self, url: str, status: int | None, message: str):
        self.url, self.status = url, status
        super().__init__(f"{message} (url={url}, status={status})")


@dataclass
class FetchResult:
    url: str
    final_url: str
    status: int
    text: str
    content_type: str
    from_cache: bool
    fetched_at: str  # ISO timestamp of the original retrieval
    headers: dict  # selected response headers (lowercased)


class _HostState:
    """Per-host politeness: serialize requests and remember refusals."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.next_ok = 0.0
        self.refused = False


class PoliteFetcher:
    def __init__(
        self,
        cache_dir: str | Path,
        *,
        delay: float = DEFAULT_DELAY,
        jitter: float = DEFAULT_JITTER,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = 2,
        respect_robots: bool = True,
        offline: bool = False,
        transport: httpx.BaseTransport | None = None,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.delay, self.jitter = delay, jitter
        self.max_retries = max_retries
        self.respect_robots = respect_robots
        self.offline = offline
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en"},
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
        )
        self._hosts: dict[str, _HostState] = {}
        self._hosts_lock = threading.Lock()
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._global_lock = threading.Lock()  # never more than one live request overall

    # -- cache ---------------------------------------------------------------

    def _cache_path(self, url: str, params: dict | None) -> Path:
        key = url + (json.dumps(params, sort_keys=True) if params else "")
        return self.cache_dir / (hashlib.sha1(key.encode()).hexdigest() + ".json")

    @staticmethod
    def _read_cache(path: Path) -> dict | None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    @staticmethod
    def _write_cache(path: Path, record: dict) -> None:
        path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    # -- politeness ------------------------------------------------------------

    def _host_state(self, url: str) -> _HostState:
        host = urlparse(url).netloc
        with self._hosts_lock:
            return self._hosts.setdefault(host, _HostState())

    def _wait_slot(self, state: _HostState) -> None:
        """Reserve the next request slot for this host; sleep until it opens."""
        with state.lock:
            now = time.monotonic()
            wait = max(0.0, state.next_ok - now)
            state.next_ok = max(now, state.next_ok) + self.delay + random.uniform(0, self.jitter)
        if wait:
            time.sleep(wait)

    # -- robots ----------------------------------------------------------------

    def robots_allows(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        if robots_url not in self._robots:
            state = self._host_state(robots_url)
            self._wait_slot(state)
            with self._global_lock:
                try:
                    resp = self._client.get(robots_url)
                except httpx.HTTPError:
                    parser = None  # unreachable: be conservative
                else:
                    if resp.status_code == 200 and resp.text.strip():
                        parser = urllib.robotparser.RobotFileParser()
                        parser.parse(resp.text.splitlines())
                    elif resp.status_code == 404:
                        parser = None  # no robots rules: allowed
                    else:  # 403, 5xx... treat as a signal not to crawl
                        state.refused = True
                        parser = "denied"
            self._robots[robots_url] = parser
        parser = self._robots[robots_url]
        if parser in (None, "denied"):
            return parser is None
        return parser.can_fetch(USER_AGENT, url)

    # -- fetch -------------------------------------------------------------------

    def get(self, url: str, *, params: dict | None = None, force: bool = False) -> FetchResult:
        cache_path = self._cache_path(url, params)
        if not force:
            cached = self._read_cache(cache_path)
            if cached:
                return FetchResult(
                    url=cached["url"],
                    final_url=cached.get("final_url", cached["url"]),
                    status=cached["status"],
                    text=cached["text"],
                    content_type=cached.get("content_type", ""),
                    from_cache=True,
                    fetched_at=cached["fetched_at"],
                    headers=cached.get("headers", {}),
                )
        if self.offline:
            raise FetchFailed(url, None, "offline mode and no cached response")

        state = self._host_state(url)
        if state.refused:
            raise FetchRefused(f"{urlparse(url).netloc} refused automated access earlier this session")
        if not self.robots_allows(url):
            raise FetchRefused(f"robots.txt disallows {url}")

        backoff = 5.0
        last_error: str | None = None
        for attempt in range(self.max_retries + 1):
            self._wait_slot(state)
            with self._global_lock:
                try:
                    resp = self._client.get(url, params=params)
                except httpx.HTTPError as exc:
                    last_error = f"network error: {exc}"
                    time.sleep(backoff)
                    backoff *= 2
                    continue
            if resp.status_code == 403:
                state.refused = True
                raise FetchRefused(f"403 for {url} - not retrying")
            if resp.status_code == 429 or resp.status_code >= 500:
                last_error = f"HTTP {resp.status_code}"
                retry_after = resp.headers.get("Retry-After")
                time.sleep(float(retry_after) if retry_after and retry_after.isdigit() else backoff)
                backoff *= 2
                continue
            if resp.status_code >= 400:
                raise FetchFailed(url, resp.status_code, "client error")
            record = {
                "url": url,
                "final_url": str(resp.url),
                "status": resp.status_code,
                "content_type": resp.headers.get("content-type", ""),
                "fetched_at": datetime.now(UTC).isoformat(),
                "text": resp.text,
                # raw bytes kept for anything text decoding mangles
                "content_b64": base64.b64encode(resp.content).decode("ascii"),
                "headers": {h: resp.headers.get(h, "") for h in KEPT_HEADERS if resp.headers.get(h)},
            }
            self._write_cache(cache_path, record)
            return FetchResult(
                url=url,
                final_url=str(resp.url),
                status=resp.status_code,
                text=resp.text,
                content_type=record["content_type"],
                from_cache=False,
                fetched_at=record["fetched_at"],
                headers=record["headers"],
            )
        raise FetchFailed(url, None, f"gave up after {self.max_retries + 1} attempts: {last_error}")

    def close(self) -> None:
        self._client.close()
