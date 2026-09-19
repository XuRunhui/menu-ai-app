"""In-memory rate limiting for LLM/paid-API endpoints on the public demo deployment.

All disabled when set to 0 (the default for local development):
- ``demo_rate_limit_per_hour``: requests per client IP in a rolling hour.
- ``demo_daily_request_cap``: total requests across all clients per UTC day,
  a hard ceiling on API spend if the demo link gets shared widely.
- ``demo_dish_image_rate_limit_per_hour`` / ``demo_dish_image_daily_cap``: the same two for
  dish-photo searches, which a menu page makes one per dish.
- ``demo_combine_rate_limit_per_hour``: menu combining, which costs CPU rather than money.
- ``demo_menus_per_hour``, ``demo_llm_calls_per_hour`` / ``demo_llm_calls_per_day``: site-wide
  ceilings on menus read and DeepSeek calls, for traffic that rotates addresses to get round the
  per-IP limits. A DeepSeek call past its budget raises ``DemoCapReached`` from the LLM client.

State lives in process memory, which is fine for a single-container demo.
"""

import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import HTTPException, Request

from app.core.config import settings

_lock = threading.Lock()


class DemoCapReached(HTTPException):
    """A demo limit was reached. An HTTPException (429), so an endpoint that doesn't catch it
    answers 429, while code built to fall back on any error (the scripted assistant) still does."""

    def __init__(self, detail: str):
        super().__init__(status_code=429, detail=detail)

_hits_by_ip: dict[str, deque[float]] = defaultdict(deque)
_daily = {"day": "", "count": 0}


def client_ip(request: Request) -> str:
    """The visitor's address as the hosting platform saw it, which the visitor can't choose.

    Cloud Run appends the address a request came from to X-Forwarded-For, and the Next.js proxy
    passes the header on untouched, so the right-most entry is the real one. Everything to its
    left is whatever the client sent: this used to read the first entry, which let anyone pose as
    a new visitor on every request by sending their own header (tested on the live site).
    """
    forwarded = [part.strip() for part in request.headers.get("x-forwarded-for", "").split(",") if part.strip()]
    hops = max(1, settings.trusted_proxy_hops)
    if len(forwarded) >= hops:
        return forwarded[-hops]
    if forwarded:
        return forwarded[0]
    return request.client.host if request.client else "unknown"


_dish_image_hits: dict[str, deque[float]] = defaultdict(deque)
_dish_image_daily = {"day": "", "count": 0}
_combine_hits: dict[str, deque[float]] = defaultdict(deque)


def _limit(key: str, hits_by_key, per_hour: int, message: str,
           daily: dict | None = None, daily_cap: int = 0, daily_message: str = "") -> None:
    """Allow ``per_hour`` hits per key in a rolling hour and ``daily_cap`` a UTC day in all, or
    raise 429. A refused request counts toward neither."""
    if per_hour <= 0 and daily_cap <= 0:
        return
    now = time.time()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with _lock:
        if daily is not None and daily_cap > 0:
            if daily["day"] != today:
                daily["day"], daily["count"] = today, 0
            if daily["count"] >= daily_cap:
                raise DemoCapReached(daily_message)
        if per_hour > 0:
            hits = hits_by_key[key]
            while hits and now - hits[0] > 3600:
                hits.popleft()
            if len(hits) >= per_hour:
                raise DemoCapReached(message)
            hits.append(now)
        if daily is not None and daily_cap > 0:
            daily["count"] += 1


async def enforce_dish_image_limit(request: Request) -> None:
    """Per-IP cap on dish-photo lookups.

    Separate from the main demo budget because one menu page legitimately asks for dozens of
    photos at once; that shouldn't burn an hour's allowance of menu parses and chat turns.
    """
    _limit(client_ip(request), _dish_image_hits, settings.demo_dish_image_rate_limit_per_hour,
           "Too many image requests. Please try again later.",
           _dish_image_daily, settings.demo_dish_image_daily_cap,
           "The demo has found all the dish photos it can for today. Please try again tomorrow.")


async def enforce_combine_limit(request: Request) -> None:
    """Per-IP cap on menu combining (CPU only, no API spend)."""
    _limit(client_ip(request), _combine_hits, settings.demo_combine_rate_limit_per_hour,
           "Too many requests from this browser. Please wait a few minutes and try again.")


async def enforce_demo_limits(request: Request) -> None:
    """FastAPI dependency that raises 429 when a demo limit is exceeded."""
    _limit(client_ip(request), _hits_by_ip, settings.demo_rate_limit_per_hour,
           "Too many requests from this browser. Please wait a few minutes and try again.",
           _daily, settings.demo_daily_request_cap,
           "The demo has reached its daily usage limit. Please try again tomorrow.")


# ─── Site-wide ceilings ─────────────────────────────────────────────────────────

_SITE = "site"
_menu_reads: dict[str, deque[float]] = defaultdict(deque)
_llm_calls: dict[str, deque[float]] = defaultdict(deque)
_llm_daily = {"day": "", "count": 0}


def claim_menu_read() -> None:
    """Take one of the menus the whole site may read this hour: a new photo parse or a restaurant
    menu lookup. Per-visitor limits stop one visitor; this stops everyone together."""
    _limit(_SITE, _menu_reads, settings.demo_menus_per_hour,
           "The demo has read as many menus as it can this hour. Please try again a little later.")


def claim_llm_call() -> None:
    """Take one DeepSeek call from the site-wide budget. Every call goes through LLMClient, which
    asks here first; cached answers never reach it."""
    _limit(_SITE, _llm_calls, settings.demo_llm_calls_per_hour,
           "The demo's AI is busy for the rest of this hour. Please try again a little later.",
           _llm_daily, settings.demo_llm_calls_per_day,
           "The demo's AI has done all it can for today. Please try again tomorrow.")


_places_calls: dict[str, deque[float]] = defaultdict(deque)
_places_daily = {"day": "", "count": 0}


def claim_places_call() -> None:
    """Take one Google Places request from the site-wide daily budget."""
    _limit(_SITE, _places_calls, 0, "", _places_daily, settings.demo_places_calls_per_day,
           "The demo has looked up all the restaurants it can for today. Please try again tomorrow.")


def llm_budget_exhausted() -> bool:
    """Whether a DeepSeek call would be refused right now. Lets a feature that fell back to a
    cheaper answer (combos without the model, say) avoid caching it as the real one."""
    now = time.time()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with _lock:
        per_hour, daily_cap = settings.demo_llm_calls_per_hour, settings.demo_llm_calls_per_day
        recent = sum(1 for hit in _llm_calls[_SITE] if now - hit <= 3600)
        return bool((per_hour > 0 and recent >= per_hour) or
                    (daily_cap > 0 and _llm_daily["day"] == today and _llm_daily["count"] >= daily_cap))


def reset_demo_limits() -> None:
    """Clear limiter state (used by tests)."""
    with _lock:
        _hits_by_ip.clear()
        _dish_image_hits.clear()
        _combine_hits.clear()
        _menu_reads.clear()
        _llm_calls.clear()
        _daily["day"], _daily["count"] = "", 0
        _llm_daily["day"], _llm_daily["count"] = "", 0
        _places_daily["day"], _places_daily["count"] = "", 0
        _dish_image_daily["day"], _dish_image_daily["count"] = "", 0
