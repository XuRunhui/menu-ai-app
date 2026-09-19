"""In-memory rate limiting for LLM/paid-API endpoints on the public demo deployment.

Two limits, both disabled when set to 0 (the default for local development):
- ``demo_rate_limit_per_hour``: requests per client IP in a rolling hour.
- ``demo_daily_request_cap``: total requests across all clients per UTC day,
  a hard ceiling on API spend if the demo link gets shared widely.

State lives in process memory, which is fine for a single-container demo.
"""

import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import HTTPException, Request

from app.core.config import settings

_lock = threading.Lock()
_hits_by_ip: dict[str, deque[float]] = defaultdict(deque)
_daily = {"day": "", "count": 0}


def client_ip(request: Request) -> str:
    # Behind the HF/Next.js proxies the real client is the first X-Forwarded-For entry.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


_dish_image_hits: dict[str, deque[float]] = defaultdict(deque)


def _rolling_limit(hits_by_ip, request: Request, per_hour: int, message: str) -> None:
    """Allow ``per_hour`` requests per IP in a rolling hour, or raise 429."""
    if per_hour <= 0:
        return
    now = time.time()
    with _lock:
        hits = hits_by_ip[client_ip(request)]
        while hits and now - hits[0] > 3600:
            hits.popleft()
        if len(hits) >= per_hour:
            raise HTTPException(status_code=429, detail=message)
        hits.append(now)


async def enforce_dish_image_limit(request: Request) -> None:
    """Per-IP cap on dish-photo lookups.

    Separate from the main demo budget because one menu page legitimately asks for dozens of
    photos at once; that shouldn't burn an hour's allowance of menu parses and chat turns.
    """
    _rolling_limit(_dish_image_hits, request, settings.demo_dish_image_rate_limit_per_hour,
                   "Too many image requests. Please try again later.")


async def enforce_demo_limits(request: Request) -> None:
    """FastAPI dependency that raises 429 when a demo limit is exceeded."""
    per_hour = settings.demo_rate_limit_per_hour
    daily_cap = settings.demo_daily_request_cap
    if per_hour <= 0 and daily_cap <= 0:
        return

    now = time.time()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    with _lock:
        if daily_cap > 0:
            if _daily["day"] != today:
                _daily["day"], _daily["count"] = today, 0
            if _daily["count"] >= daily_cap:
                raise HTTPException(
                    status_code=429,
                    detail="The demo has reached its daily usage limit. Please try again tomorrow.",
                )

        if per_hour > 0:
            hits = _hits_by_ip[client_ip(request)]
            while hits and now - hits[0] > 3600:
                hits.popleft()
            if len(hits) >= per_hour:
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests from this browser. Please wait a few minutes and try again.",
                )
            hits.append(now)

        if daily_cap > 0:
            _daily["count"] += 1


def reset_demo_limits() -> None:
    """Clear limiter state (used by tests)."""
    with _lock:
        _hits_by_ip.clear()
        _dish_image_hits.clear()
        _daily["day"], _daily["count"] = "", 0
