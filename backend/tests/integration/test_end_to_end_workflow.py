"""Integration tests for end-to-end RAG workflow."""

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
from app.services.recommendation.taste_texture_predictor import TasteTexturePredictor  # noqa: E402


@pytest.mark.integration
@pytest.mark.anyio
async def test_complete_recommendation_workflow():
    """Run a full workflow using real API keys when available."""
    if not os.getenv("RUN_INTEGRATION_TESTS"):
        pytest.skip("Set RUN_INTEGRATION_TESTS=1 to run integration tests")

    llm_key = os.getenv("DEEPSEEK_API_KEY")
    if not llm_key:
        pytest.skip("DEEPSEEK_API_KEY not set")

    google_key = os.getenv("GOOGLE_PLACES_API_KEY")
    yelp_key = os.getenv("YELP_API_KEY")
    place_id = os.getenv("GOOGLE_PLACE_ID")

    engine = RAGRecommendationEngine(
        llm_api_key=llm_key,
        google_places_api_key=google_key,
        yelp_api_key=yelp_key
    )

    stats = await engine.build_knowledge_base(
        restaurant_name="Tartine Bakery",
        location="San Francisco",
        place_id=place_id
    )

    assert stats["total_documents"] >= 1
    assert stats["successful_sources"] >= 1

    recs = engine.recommend_dishes("bread pastries", top_k=2, use_llm=False)
    assert recs

    top_rec = recs[0]
    context = engine.get_dish_context(top_rec["dish_name"])
    assert context is not None

    predictor = TasteTexturePredictor(api_key=llm_key)
    round1 = await predictor.predict_round1(
        top_rec["dish_name"],
        context.get("menu_description", "") or "Popular bakery item"
    )
    assert round1["round"] == 1
