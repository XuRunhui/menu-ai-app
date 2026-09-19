"""ORM models for the application database (users, shared caches, per-user saved data).

Shared caches hold public web data and model outputs that are safe to reuse across users.
Google Places content (reviews, photos, ratings, details) is intentionally never stored:
the Places API policies only allow caching place IDs.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ─── Users ──────────────────────────────────────────────────────────────────────


class User(Base):
    """Registered user. Only an Argon2id hash of the password is stored, never the password."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Stored lowercase so "Alice" and "alice" can't both register.
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    # Null for accounts created through Google sign-in.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ─── Shared caches ──────────────────────────────────────────────────────────────


class ImageCache(Base):
    """Dish image found by web search and saved under backend/.cache/dish_images/."""

    __tablename__ = "image_cache"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    restaurant: Mapped[str] = mapped_column(String(255), default="")
    dish: Mapped[str] = mapped_column(String(255))
    query: Mapped[str] = mapped_column(String(512))
    filename: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str] = mapped_column(Text)
    # Which provider found it, and the credit line CC-licensed photos require.
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    attribution: Mapped[str | None] = mapped_column(Text, nullable=True)
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class ImageSearchFailure(Base):
    """Recent failed image search, so a rate-limited search isn't retried by every request."""

    __tablename__ = "image_search_failures"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    restaurant: Mapped[str] = mapped_column(String(255), default="")
    dish: Mapped[str] = mapped_column(String(255))
    reason: Mapped[str] = mapped_column(String(512))
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    failed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class WebSearchCache(Base):
    """DuckDuckGo review snippets and image URLs collected for a restaurant."""

    __tablename__ = "web_search_cache"

    key: Mapped[str] = mapped_column(String(512), primary_key=True)
    restaurant: Mapped[str] = mapped_column(String(255))
    location: Mapped[str] = mapped_column(String(512), default="")
    payload: Mapped[dict] = mapped_column(JSON)
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class LLMCache(Base):
    """Model response for an exact prompt (+ image hash), reused instead of calling the API again."""

    __tablename__ = "llm_cache"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    model: Mapped[str] = mapped_column(String(128))
    purpose: Mapped[str] = mapped_column(String(64), default="")
    response_text: Mapped[str] = mapped_column(Text)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class EmbeddingCache(Base):
    """Embedding vector for a text, keyed by model + dimension + text hash."""

    __tablename__ = "embedding_cache"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    model: Mapped[str] = mapped_column(String(128))
    dimensions: Mapped[int] = mapped_column(Integer)
    vector: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Place(Base):
    """Google place IDs the app has looked up (the only Places data allowed to be stored)."""

    __tablename__ = "places"

    place_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    lookup_count: Mapped[int] = mapped_column(Integer, default=1)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RequestLog(Base):
    """One API request: who, what, how long, and how many DeepSeek tokens it used."""

    __tablename__ = "request_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    method: Mapped[str] = mapped_column(String(8))
    path: Mapped[str] = mapped_column(String(512))
    status_code: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[float] = mapped_column(Float)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    llm_calls: Mapped[int] = mapped_column(Integer, default=0)
    llm_cache_hits: Mapped[int] = mapped_column(Integer, default=0)
    llm_prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    llm_completion_tokens: Mapped[int] = mapped_column(Integer, default=0)


class MenuParseCache(Base):
    """Parsed menu shared by everyone who uploads the same image (same translation, same model).

    ``id`` is random and unguessable; it appears in result URLs (/results?menu=<id>) so a page
    can be restored after a refresh.
    """

    __tablename__ = "menu_parse_cache"
    __table_args__ = (UniqueConstraint("image_sha256", "target_language", "model"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    image_sha256: Mapped[str] = mapped_column(String(64))
    target_language: Mapped[str] = mapped_column(String(64), default="")
    model: Mapped[str] = mapped_column(String(128))
    restaurant_name: Mapped[str] = mapped_column(String(255), default="")
    detected_language: Mapped[str | None] = mapped_column(String(64), nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    parsed_menu: Mapped[dict] = mapped_column(JSON)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


# ─── Per-user saved data (signed-in users only) ─────────────────────────────────


class SavedMenu(Base):
    """A menu a signed-in user parsed; also serves as that user's parse cache."""

    __tablename__ = "saved_menus"
    __table_args__ = (UniqueConstraint("user_id", "image_sha256", "target_language"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    image_sha256: Mapped[str] = mapped_column(String(64))
    # "" when no translation was requested (NULLs don't participate in unique constraints).
    target_language: Mapped[str] = mapped_column(String(64), default="")
    # Id of the shared menu_parse_cache row; used in /results?menu=<id> links.
    menu_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    restaurant_name: Mapped[str] = mapped_column(String(255), default="")
    detected_language: Mapped[str | None] = mapped_column(String(64), nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    parsed_menu: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RestaurantHistory(Base):
    """A restaurant a signed-in user opened. Stores the place ID and the user's own search text."""

    __tablename__ = "restaurant_history"
    __table_args__ = (UniqueConstraint("user_id", "place_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    place_id: Mapped[str] = mapped_column(String(255))
    label: Mapped[str] = mapped_column(String(255), default="")
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
