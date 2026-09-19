"""Unit tests for recommendation API endpoints."""

import os
import sys

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("pydantic_settings")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.api.v1.endpoints import recommendation as rec_api  # noqa: E402
from app.core.config import settings  # noqa: E402


class _FakeEngine:
    def __init__(self, llm_api_key=None, google_places_api_key=None, yelp_api_key=None, **kwargs):
        self.knowledge_base_built = False
        self.dish_names = ["Ramen", "Salad"]

    async def build_knowledge_base(self, restaurant_name, location, place_id=None, parsed_menu=None):
        self.knowledge_base_built = True
        return {
            "total_documents": 3,
            "menu_items": 1,
            "review_mentions": 1,
            "unique_dishes": 2,
            "sources": ["DuckDuckGo"],
            "successful_sources": 1,
            "failed_sources": []
        }

    def recommend_dishes(self, user_preferences, top_k=5, use_llm=True):
        return [
            {
                "dish_name": "Ramen",
                "confidence": 0.9,
                "reasons": ["Spicy and popular"],
                "review_count": 3,
                "data_sources": ["DuckDuckGo"],
                "metadata": {"spicy_level": 2, "allergens": ["gluten"], "dietary_tags": []}
            }
        ][:top_k]

    def get_dish_context(self, dish_name):
        return {
            "dish_name": dish_name,
            "menu_description": "Spicy noodles with rich broth",
            "review_count": 2,
            "review_excerpts": ["Rich broth", "Spicy but balanced"],
            "metadata": {"spicy_level": 2},
            "is_popular": True
        }


class _FakePredictor:
    def __init__(self, api_key=None, model_name=None):
        self.api_key = api_key
        self.model_name = model_name

    async def predict_round1(self, dish_name, description):
        return {
            "tastes": ["spicy", "umami"],
            "textures": ["soft"],
            "flavor_profile": "Rich and spicy",
            "confidence": 0.7,
            "round": 1
        }

    async def predict_round2(self, dish_name, description, review_excerpts, round1_prediction):
        return {
            "tastes": ["spicy", "umami", "rich"],
            "textures": ["soft", "tender"],
            "flavor_profile": "Rich and spicy with tender texture",
            "confidence": 0.85,
            "round": 2,
            "changes_from_round1": ["Added 'rich' based on reviews"]
        }


def _create_client():
    app = FastAPI()
    app.include_router(rec_api.router, prefix="/api/v1/recommendation")
    return TestClient(app)


def _reset_engine_cache():
    rec_api._ENGINE_CACHE.clear()
    rec_api._LAST_ENGINE_KEY = None


def test_build_kb_endpoint(monkeypatch):
    """Build knowledge base endpoint returns stats."""
    monkeypatch.setattr(rec_api, "RAGRecommendationEngine", _FakeEngine)
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    _reset_engine_cache()

    client = _create_client()
    response = client.post(
        "/api/v1/recommendation/build-knowledge-base",
        json={"restaurant_name": "Test Place", "location": "SF"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["total_documents"] == 3


def test_recommend_endpoint(monkeypatch):
    """Recommend endpoint returns recommendations."""
    monkeypatch.setattr(rec_api, "RAGRecommendationEngine", _FakeEngine)
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    _reset_engine_cache()

    client = _create_client()
    response = client.post(
        "/api/v1/recommendation/recommend",
        json={
            "restaurant_name": "Test Place",
            "location": "SF",
            "user_preferences": "spicy noodles",
            "top_k": 1
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["recommendations"]
    assert data["recommendations"][0]["dish_name"] == "Ramen"


def test_taste_texture_endpoint(monkeypatch):
    """Taste/texture endpoint returns round 1 prediction."""
    monkeypatch.setattr(rec_api, "TasteTexturePredictor", _FakePredictor)
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    _reset_engine_cache()

    client = _create_client()
    response = client.post(
        "/api/v1/recommendation/taste-texture",
        json={
            "dish_name": "Ramen",
            "description": "Spicy noodles",
            "include_reviews": False
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["round1"]["round"] == 1
    assert data["round2"] is None


def test_endpoint_missing_api_key(monkeypatch):
    """Endpoints fail gracefully without API keys."""
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    _reset_engine_cache()

    client = _create_client()
    response = client.post(
        "/api/v1/recommendation/taste-texture",
        json={
            "dish_name": "Ramen",
            "description": "Spicy noodles",
            "include_reviews": False
        }
    )

    assert response.status_code == 500
    assert "DEEPSEEK_API_KEY" in response.text


def test_demo_rate_limit_returns_429(monkeypatch):
    """Per-IP demo limit rejects requests beyond the hourly quota."""
    from app.core import rate_limit

    monkeypatch.setattr(rec_api, "TasteTexturePredictor", _FakePredictor)
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    monkeypatch.setattr(settings, "demo_rate_limit_per_hour", 2)
    rate_limit.reset_demo_limits()

    client = _create_client()
    payload = {"dish_name": "Ramen", "description": "Spicy noodles", "include_reviews": False}
    codes = [
        client.post("/api/v1/recommendation/taste-texture", json=payload).status_code
        for _ in range(3)
    ]
    rate_limit.reset_demo_limits()

    assert codes == [200, 200, 429]
