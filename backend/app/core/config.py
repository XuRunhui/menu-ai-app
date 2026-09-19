"""Application configuration from environment variables."""

import os
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    # deepseek-flash is DeepSeek's multimodal model; LLMClient runs it in non-thinking mode.
    deepseek_model: str = "deepseek-flash"
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_max_tokens: int = 8192
    deepseek_timeout_seconds: float = 120.0
    yelp_api_key: str = os.getenv("YELP_API_KEY", "")
    google_places_api_key: str = os.getenv("GOOGLE_PLACES_API_KEY", "")
    # Dish photos: let DeepSeek pick the right photo out of the search results (see image_judge.py).
    # Off falls back to "first result that downloads", which is what produced the wrong photos.
    dish_image_judge_enabled: bool = True
    dish_image_candidates: int = 6          # validated photos put in front of the model
    dish_image_judge_batch_size: int = 6    # images per request (DeepSeek accepts up to 600)
    rag_embedding_model: str = "all-MiniLM-L6-v2"
    rag_top_k_default: int = 5
    rag_use_llm_enhancement: bool = True
    rag_cache_enabled: bool = True
    rag_cache_ttl_seconds: int = 604800
    cors_origins: list[str] = ["http://localhost:3000"]
    # Databases: SQLite files under backend/.data by default; any SQLAlchemy URL works (e.g. Postgres)
    database_url: str = ""
    # Reference knowledge (Wikidata, FlavorGraph, cookbooks); rebuilt by `python -m app.knowledge.cli build`
    knowledge_database_url: str = ""
    # Accounts (register/login/Google/history on the server). Off: everyone uses the app as a guest.
    auth_enabled: bool = False
    # Auth: set AUTH_SECRET_KEY in production (e.g. `openssl rand -hex 32`) so sessions survive restarts
    auth_secret_key: str = ""
    auth_session_days: int = 7
    # Google sign-in: OAuth 2.0 Web client ID from Google Cloud Console (leave empty to hide the button)
    google_oauth_client_id: str = ""
    # Public demo guards for LLM/paid-API endpoints (0 disables; see app/core/rate_limit.py)
    demo_rate_limit_per_hour: int = 0
    demo_daily_request_cap: int = 0
    # Per-IP cap on dish-image lookups. A menu page fires one per dish, and each miss now costs a
    # DeepSeek call to choose the photo, so this is set well above one page and below a scripted loop.
    demo_dish_image_rate_limit_per_hour: int = 0

    # Keys pasted into .env or a secret manager often carry a trailing newline or spaces,
    # which the APIs then reject with a confusing error.
    @field_validator("deepseek_api_key", "google_places_api_key", "yelp_api_key",
                     "auth_secret_key", "google_oauth_client_id", mode="before")
    @classmethod
    def _strip_whitespace(cls, value):
        return value.strip() if isinstance(value, str) else value

    @staticmethod
    def _default_sqlite_url(filename: str) -> str:
        data_dir = Path(__file__).resolve().parents[2] / ".data"
        data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{data_dir / filename}"

    @property
    def resolved_database_url(self) -> str:
        return self.database_url or self._default_sqlite_url("menuist.db")

    @property
    def resolved_knowledge_database_url(self) -> str:
        return self.knowledge_database_url or self._default_sqlite_url("knowledge.db")

    class Config:
        # Look for .env file in the parent directory (menu-ai-app root)
        env_file = Path(__file__).parent.parent.parent.parent / ".env"
        case_sensitive = False
        # Ignore unrelated/legacy keys in .env (e.g. an old GEMINI_API_KEY) instead of crashing.
        extra = "ignore"


settings = Settings()
