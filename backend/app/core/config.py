"""Application configuration from environment variables."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = "gemini-2.5-flash"
    yelp_api_key: str = os.getenv("YELP_API_KEY", "")
    google_places_api_key: str = os.getenv("GOOGLE_PLACES_API_KEY", "")
    cors_origins: list[str] = ["http://localhost:3000"]

    class Config:
        # Look for .env file in the parent directory (menu-ai-app root)
        env_file = Path(__file__).parent.parent.parent.parent / ".env"
        case_sensitive = False


settings = Settings()
