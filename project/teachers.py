"""Multi-provider teacher pool with quota-aware state (v2 brief sections 17A/17B).

Implements:
- provider pool from config/teachers.yaml (Gemini slots, OpenRouter, Z.ai,
  legacy TEACHER_* fallback), keys resolved from environment variables
- independent per-provider/per-credential usage tracking with configurable
  operating budgets and safety margins (never run at provider ceilings)
- rotation to the next provider of the requested role when one is exhausted
  (the configured Gemini keys belong to separate projects: independent
  scheduling is legitimate; rotation never bypasses a provider's own limits)
- Retry-After respected, exponential backoff, no tight retry loops
- persistence of usage state across runs (data/annotations/provider_state.json)
"""

from __future__ import annotations

import json
import os
import time
from collections import deque
from datetime import UTC, datetime
from pathlib import Path

import httpx
import yaml

from project.freeze_corpus import PROJECT_ROOT

TEACHERS_CONFIG = PROJECT_ROOT / "config" / "teachers.yaml"
STATE_PATH = PROJECT_ROOT / "data" / "annotations" / "provider_state.json"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


def load_env(dotenv: Path = PROJECT_ROOT / ".env") -> None:
    """Populate os.environ from a .env file without overriding real env vars."""
    if not dotenv.exists():
        return
    for line in dotenv.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


class QuotaExhausted(Exception):
    """All providers of the requested role are at their configured budget."""


class ProviderError(Exception):
    pass


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


class _Usage:
    """Rolling usage counters for one provider slot (thread-safe)."""

    def __init__(self, limits: dict, safety_margin: float):
        import threading

        self.rpm = limits.get("rpm")
        self.tpm = limits.get("tpm")
        self.rpd = limits.get("rpd")
        self.margin = safety_margin
        self.minute_window: deque[float] = deque()
        self.requests_today = 0
        self.tokens_today = 0
        self.successful = 0
        self.failed = 0
        self.last_429: str | None = None
        self.available_after: str | None = None
        self.day = _today()
        self._lock = threading.Lock()

    def _rollover(self) -> None:
        if self.day != _today():
            self.day = _today()
            self.requests_today = 0
            self.tokens_today = 0
            self.available_after = None

    @property
    def max_rpd(self) -> float:
        return (self.rpd or 10**9) * self.margin

    @property
    def max_rpm(self) -> float:
        return (self.rpm or 10**9) * self.margin

    def budget_left(self) -> bool:
        with self._lock:
            self._rollover()
            if self.available_after and _today() >= self.available_after:
                self.available_after = None
            if self.available_after:
                return False
            if self.requests_today >= self.max_rpd:
                return False
            current_minute = int(time.time() // 60)
            return sum(1 for t in self.minute_window if int(t // 60) == current_minute) < self.max_rpm

    def try_reserve(self) -> bool:
        """Atomically check the budget AND reserve a request slot.

        Uses Google's enforcement window — the CALENDAR minute — not a rolling
        60s window: a rolling window can burst ~2x the limit across a minute
        boundary (observed as a 17/15 RPM peak). Timestamps are wall-clock so
        reservations survive process restarts (monotonic time does not).
        """
        with self._lock:
            self._rollover()
            if self.available_after:
                if _today() >= self.available_after:
                    self.available_after = None
                else:
                    return False
            if self.requests_today >= self.max_rpd:
                return False
            now = time.time()
            current_minute = int(now // 60)
            if self.minute_window and int(self.minute_window[-1] // 60) != current_minute:
                self.minute_window.clear()  # new calendar minute
            if len(self.minute_window) >= self.max_rpm:
                return False
            self.minute_window.append(now)
            return True

    def daily_dry(self) -> bool:
        """True when the daily budget is spent (vs a transient minute-window cooldown)."""
        with self._lock:
            self._rollover()
            return self.requests_today >= self.max_rpd or bool(self.available_after)

    def record_result(self, *, ok: bool, tokens: int = 0, retry_after: str | None = None) -> None:
        with self._lock:
            self._rollover()
            if ok:
                self.successful += 1
                self.requests_today += 1
                self.tokens_today += tokens
            else:
                self.failed += 1
                if retry_after:
                    self.last_429 = datetime.now(UTC).isoformat()
                    self.available_after = retry_after

    def to_dict(self) -> dict:
        return {
            "day": self.day,
            "minute_window": list(self.minute_window),
            "requests_today": self.requests_today,
            "tokens_today": self.tokens_today,
            "successful": self.successful,
            "failed": self.failed,
            "last_429": self.last_429,
            "available_after": self.available_after,
        }

    @classmethod
    def from_dict(cls, data: dict, limits: dict, margin: float) -> _Usage:
        usage = cls(limits, margin)
        usage.day = data.get("day", _today())
        usage.minute_window = deque(data.get("minute_window", []))
        usage.requests_today = data.get("requests_today", 0)
        usage.tokens_today = data.get("tokens_today", 0)
        usage.successful = data.get("successful", 0)
        usage.failed = data.get("failed", 0)
        usage.last_429 = data.get("last_429")
        usage.available_after = data.get("available_after")
        return usage


class TeacherPool:
    def __init__(self, config_path: Path = TEACHERS_CONFIG):
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        self.providers: list[dict] = []
        for spec in config["providers"]:
            key = os.environ.get(spec["api_key_env"], "")
            if not key:
                continue
            spec = dict(spec)
            spec["api_key"] = key
            spec["base_url"] = spec.get("base_url") or os.environ.get(spec.get("base_url_env", ""), "")
            spec["model"] = spec.get("model") or os.environ.get(spec.get("model_env", ""), "")
            if spec["kind"] != "gemini" and not spec["base_url"]:
                continue  # OpenAI-compatible slots need an endpoint; gemini has a fixed one
            if not spec["model"]:
                continue  # misconfigured slot; skip rather than guess
            self.providers.append(spec)
        saved = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
        for spec in self.providers:
            limits = spec.get("limits", {})
            saved_usage = saved.get(spec["name"])
            spec["usage"] = (
                _Usage.from_dict(saved_usage, limits, spec.get("safety_margin", 0.85))
                if saved_usage
                else _Usage(limits, spec.get("safety_margin", 0.85))
            )
        self._client = httpx.Client(timeout=120)

    # -- selection ------------------------------------------------------------

    def _candidates(self, roles: list[str]) -> list[dict]:
        return [
            p for p in self.providers
            if p.get("role") in roles and not p.get("disabled") and p["usage"].daily_dry() is False
        ]

    def save_state(self) -> None:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(
            json.dumps({p["name"]: p["usage"].to_dict() for p in self.providers}, indent=1),
            encoding="utf-8",
        )

    # -- calls ------------------------------------------------------------------

    def call(self, messages: list[dict], *, roles: list[str] | None = None, json_mode: bool = True, max_cooldown_seconds: float = 300.0) -> tuple[dict, str]:
        """Call the first available provider matching `roles`; returns (provider_spec, text).

        Rotates through same-role providers, honors Retry-After, backs off
        exponentially on 429/5xx (max 2 retries per provider before rotating),
        and WAITS OUT transient rate-limit cooldowns: when every matching slot
        is minute-window-clogged but no daily budget is spent, the call sleeps
        and retries rather than failing (the first full-corpus run died to a
        429 storm here). Only real daily exhaustion (or a long dry spell)
        raises QuotaExhausted.
        """
        roles = roles or ["primary"]
        attempted: set[str] = set()
        cooldown = 0.0
        while True:
            spec = next((p for p in self._candidates(roles) if p["name"] not in attempted), None)
            if spec is None:
                # everything matching is either attempted-and-failed, disabled,
                # or cooling down; distinguish daily exhaustion from transient.
                # ALL matching slots must be daily-dry: one exhausted slot must
                # not starve its siblings that still have budget (observed when
                # gemini_1 crossed its daily cap while 2-4 had ~500 left).
                if all(
                    p.get("role") in roles and (p.get("disabled") or p["usage"].daily_dry())
                    for p in self.providers
                    if p.get("role") in roles
                ):
                    self.save_state()
                    raise QuotaExhausted(f"daily budget spent on all providers for roles={roles}")
                if cooldown >= max_cooldown_seconds:
                    self.save_state()
                    raise QuotaExhausted(f"all providers cooling down for over {max_cooldown_seconds:.0f}s (roles={roles})")
                time.sleep(30.0)
                cooldown += 30.0
                attempted.clear()  # minute windows refill; try everyone again
                continue
            if not spec["usage"].try_reserve():
                attempted.add(spec["name"])
                continue
            try:
                text = self._call_one(spec, messages, json_mode)
                return spec, text
            except _RateLimited as exc:
                spec["usage"].record_result(ok=False, retry_after=exc.retry_after)
                attempted.add(spec["name"])
                self.save_state()
            except ProviderError:
                attempted.add(spec["name"])
                self.save_state()

    def _call_one(self, spec: dict, messages: list[dict], json_mode: bool) -> str:
        backoff = 4.0
        for attempt in range(3):
            try:
                if spec["kind"] == "gemini":
                    return self._call_gemini(spec, messages, json_mode)
                return self._call_openai(spec, messages, json_mode)
            except _RateLimited:
                if attempt == 2:
                    raise
                time.sleep(backoff)
                backoff *= 2
            except httpx.HTTPError as exc:
                if attempt == 2:
                    raise ProviderError(f"{spec['name']}: {exc}") from exc
                time.sleep(backoff)
                backoff *= 2
        raise ProviderError(f"{spec['name']}: retries exhausted")

    def _call_gemini(self, spec: dict, messages: list[dict], json_mode: bool) -> str:
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        user = "\n\n".join(m["content"] for m in messages if m["role"] == "user")
        body: dict = {
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.1},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        resp = self._client.post(
            f"{GEMINI_BASE}/models/{spec['model']}:generateContent",
            headers={"x-goog-api-key": spec["api_key"]},
            json=body,
        )
        if resp.status_code == 429:
            raise _RateLimited(spec["name"], resp.headers.get("Retry-After"))
        if resp.status_code == 403:
            raise _RateLimited(spec["name"], None)  # daily cap surfaces as 403 on free tier
        if resp.status_code >= 400:
            raise ProviderError(f"{spec['name']}: HTTP {resp.status_code}: {resp.text[:200]}")
        payload = resp.json()
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
        tokens = payload.get("usageMetadata", {}).get("totalTokenCount", 0)
        spec["usage"].record_result(ok=True, tokens=tokens)
        return text

    def _call_openai(self, spec: dict, messages: list[dict], json_mode: bool) -> str:
        body: dict = {"model": spec["model"], "messages": messages, "temperature": 0.1}
        if json_mode and spec.get("json_mode", True):
            body["response_format"] = {"type": "json_object"}
        resp = self._client.post(
            f"{spec['base_url'].rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {spec['api_key']}"},
            json=body,
        )
        if resp.status_code in (429, 403):
            if "insufficient balance" in resp.text.lower():
                # subscription exhausted: disable the slot for this run instead
                # of retrying into a refuser
                spec["disabled"] = True
                raise ProviderError(f"{spec['name']}: no balance - slot disabled for this run")
            raise _RateLimited(spec["name"], resp.headers.get("Retry-After"))
        if resp.status_code >= 400:
            raise ProviderError(f"{spec['name']}: HTTP {resp.status_code}: {resp.text[:200]}")
        payload = resp.json()
        text = payload["choices"][0]["message"]["content"]
        tokens = payload.get("usage", {}).get("total_tokens", 0)
        spec["usage"].record_result(ok=True, tokens=tokens)
        return text


class _RateLimited(Exception):
    def __init__(self, provider: str, retry_after: str | None):
        self.retry_after = retry_after
        super().__init__(f"{provider} rate limited (retry-after={retry_after})")
