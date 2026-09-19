"""Integration tests for multi-source resilience."""

import os
import sys

import pytest

pytest.importorskip("openai")
pytest.importorskip("sentence_transformers")
pytest.importorskip("numpy")
pytest.importorskip("requests")
pytest.importorskip("ddgs")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.services.recommendation.rag_engine import RAGRecommendationEngine  # noqa: E402


@pytest.mark.integration
@pytest.mark.anyio
async def test_system_works_with_one_source():
    """System should work with only one source available."""
    if not os.getenv("RUN_INTEGRATION_TESTS"):
        pytest.skip("Set RUN_INTEGRATION_TESTS=1 to run integration tests")

    llm_key = os.getenv("DEEPSEEK_API_KEY")
    if not llm_key:
        pytest.skip("DEEPSEEK_API_KEY not set")

    engine = RAGRecommendationEngine(
        llm_api_key=llm_key,
        google_places_api_key=None,
        yelp_api_key=None
    )

    stats = await engine.build_knowledge_base(
        restaurant_name="Tartine Bakery",
        location="San Francisco"
    )

    if stats["total_documents"] == 0:
        pytest.skip("No documents returned from sources")

    assert stats["successful_sources"] >= 1


@pytest.mark.integration
@pytest.mark.anyio
async def test_system_handles_all_failures(monkeypatch):
    """System should handle cases where all sources fail."""
    if not os.getenv("RUN_INTEGRATION_TESTS"):
        pytest.skip("Set RUN_INTEGRATION_TESTS=1 to run integration tests")

    llm_key = os.getenv("DEEPSEEK_API_KEY", "dummy")
    engine = RAGRecommendationEngine(llm_api_key=llm_key)

    async def _fake_collect_all_data(restaurant_name, location, place_id=None):
        return {
            "reviews": [],
            "images": [],
            "popular_dishes": [],
            "place_info": None,
            "sources": [],
            "metadata": {
                "successful_sources": 0,
                "failed_sources": [
                    {"source": "DuckDuckGo", "error": "network error"}
                ]
            }
        }

    monkeypatch.setattr(engine.aggregator, "collect_all_data", _fake_collect_all_data)

    stats = await engine.build_knowledge_base(
        restaurant_name="Nonexistent Place",
        location="Nowhere"
    )

    assert stats["total_documents"] == 0
    assert stats["successful_sources"] == 0
