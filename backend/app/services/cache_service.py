"""Database-backed caches shared by all users.

Every function here is best-effort: a database problem is logged and treated as a cache miss,
so caching can never break a request.
"""

from __future__ import annotations

import hashlib
import json
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

import numpy as np
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import (
    EmbeddingCache,
    ImageCache,
    ImageSearchFailure,
    LLMCache,
    MenuParseCache,
    Place,
    RequestLog,
    WebSearchCache,
)
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

IMAGE_TTL = timedelta(days=28)
IMAGE_FAILURE_TTL = timedelta(minutes=10)
# Photos were found and the judge said none shows the dish: that answer holds for days, and asking
# again every ten minutes paid for the same searches and judging on each visit to the menu. Finding
# nothing at all is different, usually a search engine refusing for a moment, so it keeps the 10 min.
IMAGE_NO_MATCH_TTL = timedelta(days=3)
NO_MATCHING_PHOTO = "no photo shows the dish"
WEB_SEARCH_TTL = timedelta(days=7)
LLM_TTL = timedelta(days=30)
MENU_PARSE_TTL = timedelta(days=90)  # counted from last use, so shared links keep working while used
REQUEST_LOG_RETENTION = timedelta(days=90)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    # SQLite returns naive datetimes even for timezone-aware columns; values are stored as UTC.
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _expired(stored_at: datetime, ttl: timedelta) -> bool:
    return _now() - _aware(stored_at) > ttl


def sha256_hex(*parts: str | bytes) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part if isinstance(part, bytes) else part.encode("utf-8"))
        digest.update(b"\x1f")  # separator so ("ab", "c") != ("a", "bc")
    return digest.hexdigest()


@contextmanager
def _session() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()


def _best_effort(action: str):
    """Decorator: log database errors and return the fallback instead of raising."""

    def wrap(func):
        def inner(*args, fallback=None, **kwargs):
            try:
                return func(*args, **kwargs)
            except SQLAlchemyError as exc:
                logger.warning("cache: %s failed (%s)", action, exc.__class__.__name__)
                return fallback

        inner.__name__ = func.__name__
        inner.__doc__ = func.__doc__
        return inner

    return wrap


# ─── Dish images ────────────────────────────────────────────────────────────────


# Bumped when the search query or the way a photo is chosen changes, so previously cached (worse)
# pictures are re-fetched instead of being served for another 28 days.
IMAGE_KEY_VERSION = "3"


def image_key(restaurant: str, dish: str) -> str:
    return sha256_hex(IMAGE_KEY_VERSION, restaurant.strip().lower(), dish.strip().lower())


@_best_effort("image cache read")
def get_image(restaurant: str, dish: str) -> ImageCache | None:
    with _session() as db:
        row = db.get(ImageCache, image_key(restaurant, dish))
        if row is None or _expired(row.cached_at, IMAGE_TTL):
            return None
        db.expunge(row)
        return row


@_best_effort("image cache write")
def set_image(
    restaurant: str, dish: str, query: str, filename: str, source_url: str,
    source: str = "", attribution: str = "",
) -> None:
    key = image_key(restaurant, dish)
    with _session() as db:
        db.merge(ImageCache(
            key=key, restaurant=restaurant, dish=dish, query=query,
            filename=filename, source_url=source_url, cached_at=_now(),
            source=source, attribution=attribution,
        ))
        failure = db.get(ImageSearchFailure, key)
        if failure is not None:
            db.delete(failure)


@_best_effort("image cache read")
def image_urls_for_restaurant(restaurant: str, except_dish: str = "") -> set[str]:
    """Source URLs of photos already shown for this restaurant's other dishes.

    Generic search terms find the same few photos: five different Reubens all landed on one photo
    of a Reuben. Excluding these makes each dish on a menu get its own picture.
    """
    if not restaurant.strip():
        return set()
    with _session() as db:
        rows = db.execute(
            select(ImageCache.source_url, ImageCache.cached_at)
            .where(func.lower(ImageCache.restaurant) == restaurant.strip().lower())
            .where(func.lower(ImageCache.dish) != except_dish.strip().lower())
        ).all()
    return {url for url, cached_at in rows if url and not _expired(cached_at, IMAGE_TTL)}


@_best_effort("image cache read")
def get_image_for_dish(dish: str) -> ImageCache | None:
    """The newest photo chosen for this dish name at any restaurant."""
    with _session() as db:
        row = db.scalars(
            select(ImageCache)
            .where(func.lower(func.trim(ImageCache.dish)) == dish.strip().lower())
            .order_by(ImageCache.cached_at.desc())
            .limit(1)
        ).first()
        if row is None or _expired(row.cached_at, IMAGE_TTL):
            return None
        db.expunge(row)
        return row


def _failure_ttl(reason: str) -> timedelta:
    return IMAGE_NO_MATCH_TTL if reason == NO_MATCHING_PHOTO else IMAGE_FAILURE_TTL


@_best_effort("image failure read")
def recent_image_failure(restaurant: str, dish: str) -> bool:
    with _session() as db:
        row = db.get(ImageSearchFailure, image_key(restaurant, dish))
        return row is not None and not _expired(row.failed_at, _failure_ttl(row.reason))


@_best_effort("image failure write")
def record_image_failure(restaurant: str, dish: str, reason: str) -> None:
    key = image_key(restaurant, dish)
    with _session() as db:
        row = db.get(ImageSearchFailure, key)
        if row is None:
            db.add(ImageSearchFailure(key=key, restaurant=restaurant, dish=dish, reason=reason[:500]))
        else:
            row.reason, row.attempts, row.failed_at = reason[:500], row.attempts + 1, _now()


# ─── Web search (DuckDuckGo) ────────────────────────────────────────────────────


def web_search_key(restaurant: str, location: str) -> str:
    return f"{restaurant.strip().lower()}::{location.strip().lower()}"


@_best_effort("web search cache read")
def get_web_search(restaurant: str, location: str) -> tuple[dict, datetime] | None:
    with _session() as db:
        row = db.get(WebSearchCache, web_search_key(restaurant, location))
        if row is None or _expired(row.cached_at, WEB_SEARCH_TTL):
            return None
        return row.payload, _aware(row.cached_at)


@_best_effort("web search cache write")
def set_web_search(restaurant: str, location: str, payload: dict) -> None:
    with _session() as db:
        db.merge(WebSearchCache(
            key=web_search_key(restaurant, location), restaurant=restaurant,
            location=location, payload=payload, cached_at=_now(),
        ))


# ─── LLM responses ──────────────────────────────────────────────────────────────


@_best_effort("llm cache read")
def get_llm_response(key: str) -> str | None:
    with _session() as db:
        row = db.get(LLMCache, key)
        if row is None or _expired(row.created_at, LLM_TTL):
            return None
        row.hit_count += 1
        return row.response_text


@_best_effort("llm cache write")
def set_llm_response(
    key: str, model: str, purpose: str, response_text: str,
    prompt_tokens: int = 0, completion_tokens: int = 0,
) -> None:
    with _session() as db:
        db.merge(LLMCache(
            key=key, model=model, purpose=purpose, response_text=response_text,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            hit_count=0, created_at=_now(),
        ))


# ─── Embeddings ─────────────────────────────────────────────────────────────────


def embedding_key(model: str, dimensions: int, text: str) -> str:
    return sha256_hex(model, str(dimensions), text)


@_best_effort("embedding cache read")
def get_embeddings(model: str, dimensions: int, texts: list[str]) -> dict[str, np.ndarray]:
    keys = {embedding_key(model, dimensions, text): text for text in texts}
    found: dict[str, np.ndarray] = {}
    with _session() as db:
        key_list = list(keys)
        # Chunk the IN clause to stay under SQLite's variable limit.
        for start in range(0, len(key_list), 500):
            rows = db.scalars(
                select(EmbeddingCache).where(EmbeddingCache.key.in_(key_list[start:start + 500]))
            )
            for row in rows:
                found[keys[row.key]] = np.frombuffer(row.vector, dtype=np.float32)
    return found


@_best_effort("embedding cache write")
def set_embeddings(model: str, dimensions: int, vectors: dict[str, np.ndarray]) -> None:
    with _session() as db:
        for text, vector in vectors.items():
            db.merge(EmbeddingCache(
                key=embedding_key(model, dimensions, text), model=model, dimensions=dimensions,
                vector=np.asarray(vector, dtype=np.float32).tobytes(),
            ))


# ─── Parsed menus ───────────────────────────────────────────────────────────────


@_best_effort("menu parse cache read")
def get_menu_parse(image_sha256: str, target_language: str | None, model: str) -> MenuParseCache | None:
    with _session() as db:
        row = db.scalar(select(MenuParseCache).where(
            MenuParseCache.image_sha256 == image_sha256,
            MenuParseCache.target_language == (target_language or ""),
            MenuParseCache.model == model,
        ))
        if row is None or _expired(row.last_used_at, MENU_PARSE_TTL):
            return None
        row.hit_count += 1
        row.last_used_at = _now()
        db.flush()
        db.expunge(row)
        return row


@_best_effort("menu parse cache write")
def set_menu_parse(
    image_sha256: str, target_language: str | None, model: str, restaurant_name: str | None,
    detected_language: str | None, item_count: int, parsed_menu: dict,
) -> str | None:
    import uuid

    with _session() as db:
        row = db.scalar(select(MenuParseCache).where(
            MenuParseCache.image_sha256 == image_sha256,
            MenuParseCache.target_language == (target_language or ""),
            MenuParseCache.model == model,
        ))
        if row is None:
            row = MenuParseCache(id=uuid.uuid4().hex, image_sha256=image_sha256,
                                 target_language=target_language or "", model=model)
            db.add(row)
        row.restaurant_name = (restaurant_name or row.restaurant_name or "").strip()[:255]
        row.detected_language = detected_language
        row.item_count = item_count
        row.parsed_menu = parsed_menu
        row.last_used_at = _now()
        return row.id


@_best_effort("menu seed")
def seed_menu_parse(
    menu_id: str, image_sha256: str, model: str, restaurant_name: str,
    detected_language: str | None, item_count: int, parsed_menu: dict,
) -> str | None:
    """Insert a pre-parsed menu (e.g. the bundled sample) unless that image is already cached."""
    with _session() as db:
        row = db.scalar(select(MenuParseCache).where(
            MenuParseCache.image_sha256 == image_sha256,
            MenuParseCache.target_language == "",
            MenuParseCache.model == model,
        ))
        if row is None:
            row = MenuParseCache(
                id=menu_id, image_sha256=image_sha256, target_language="", model=model,
                restaurant_name=restaurant_name, detected_language=detected_language,
                item_count=item_count, parsed_menu=parsed_menu,
            )
            db.add(row)
        row.last_used_at = _now()
        return row.id


@_best_effort("menu label update")
def label_menu(menu_id: str, restaurant_name: str) -> None:
    with _session() as db:
        row = db.get(MenuParseCache, menu_id)
        if row is not None and restaurant_name.strip():
            row.restaurant_name = restaurant_name.strip()[:255]


@_best_effort("menu lookup")
def get_menu_by_id(menu_id: str) -> MenuParseCache | None:
    with _session() as db:
        row = db.get(MenuParseCache, menu_id)
        if row is None or _expired(row.last_used_at, MENU_PARSE_TTL):
            return None
        db.expunge(row)
        return row


# ─── Places and request log ─────────────────────────────────────────────────────


@_best_effort("place touch")
def touch_place(place_id: str) -> None:
    with _session() as db:
        row = db.get(Place, place_id)
        if row is None:
            db.add(Place(place_id=place_id))
        else:
            row.lookup_count += 1
            row.last_seen_at = _now()


@_best_effort("request log write")
def log_request(
    method: str, path: str, status_code: int, duration_ms: float,
    user_id: int | None, usage: dict[str, int],
) -> None:
    with _session() as db:
        db.add(RequestLog(
            method=method, path=path[:512], status_code=status_code,
            duration_ms=round(duration_ms, 1), user_id=user_id,
            llm_calls=usage.get("calls", 0), llm_cache_hits=usage.get("cache_hits", 0),
            llm_prompt_tokens=usage.get("prompt_tokens", 0),
            llm_completion_tokens=usage.get("completion_tokens", 0),
        ))


# ─── Maintenance ────────────────────────────────────────────────────────────────


@_best_effort("purge expired rows")
def purge_expired() -> None:
    now = _now()
    with _session() as db:
        db.execute(delete(ImageCache).where(ImageCache.cached_at < now - IMAGE_TTL))
        db.execute(delete(ImageSearchFailure).where(ImageSearchFailure.failed_at < now - IMAGE_FAILURE_TTL,
                                                    ImageSearchFailure.reason != NO_MATCHING_PHOTO))
        db.execute(delete(ImageSearchFailure).where(ImageSearchFailure.failed_at < now - IMAGE_NO_MATCH_TTL))
        db.execute(delete(WebSearchCache).where(WebSearchCache.cached_at < now - WEB_SEARCH_TTL))
        db.execute(delete(LLMCache).where(LLMCache.created_at < now - LLM_TTL))
        db.execute(delete(MenuParseCache).where(MenuParseCache.last_used_at < now - MENU_PARSE_TTL))
        db.execute(delete(RequestLog).where(RequestLog.created_at < now - REQUEST_LOG_RETENTION))


@_best_effort("legacy cache import")
def import_legacy_json_caches(cache_dir: Path) -> int:
    """One-time import of the old JSON caches. Google content in them is skipped on purpose."""
    imported = 0
    image_db = cache_dir / "dish_image_db.json"
    with _session() as db:
        if image_db.exists() and db.scalar(select(ImageCache.key).limit(1)) is None:
            try:
                entries = json.loads(image_db.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                entries = {}
            for entry in entries.values():
                filename, dish = entry.get("filename"), entry.get("dish")
                if not filename or not dish or not (cache_dir / "dish_images" / filename).exists():
                    continue
                restaurant = entry.get("restaurant", "")
                db.merge(ImageCache(
                    key=image_key(restaurant, dish), restaurant=restaurant, dish=dish,
                    query=" ".join(p for p in [restaurant, dish, "food"] if p),
                    filename=filename, source_url=entry.get("source_url", ""),
                    cached_at=datetime.fromtimestamp(float(entry.get("cached_at", 0)), tz=timezone.utc),
                ))
                imported += 1
    if imported:
        logger.info("cache: imported %d dish images from legacy JSON cache", imported)
    return imported
