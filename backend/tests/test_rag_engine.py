"""Unit tests for RAGRecommendationEngine."""

import asyncio
import os
import sys

import pytest

pytest.importorskip("google.genai")
pytest.importorskip("sentence_transformers")
pytest.importorskip("numpy")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.recommendation.rag_engine import RAGRecommendationEngine  # noqa: E402


class _FakeVectorStore:
    def __init__(self, results=None):
        self._results = results or []
        self.added_documents = []

    def add_documents(self, documents):
        self.added_documents.extend(documents)

    def search(self, query, top_k=5, filter_dish=None):
        results = self._results
        if filter_dish:
            results = [result for result in results if result.get("dish") == filter_dish]
        return results[:top_k]


def _run(coro):
    return asyncio.run(coro)


def test_extract_dish_mentions():
    """Extract dish mentions from review text."""
    engine = RAGRecommendationEngine(gemini_api_key="dummy")
    dishes = ["Soon Tofu Jjigae", "Kimchi Pancake", "Bulgogi"]
    text = "The soon tofu was amazing! Also tried the bulgogi."

    mentions = engine._extract_dish_mentions(text, dishes)
    assert "Soon Tofu Jjigae" in mentions
    assert "Bulgogi" in mentions


def test_recommend_dishes_basic():
    """Generate recommendations without LLM enhancement."""
    engine = RAGRecommendationEngine(gemini_api_key="dummy")
    engine.knowledge_base_built = True
    engine.vector_store = _FakeVectorStore(
        results=[
            {
                "dish": "Ramen",
                "score": 0.9,
                "text": "Spicy miso ramen with pork",
                "metadata": {
                    "type": "menu_description",
                    "category": "Noodles",
                    "price": 12.5,
                    "spicy_level": 2,
                    "allergens": ["gluten"],
                    "dietary_tags": ["dairy"]
                }
            },
            {
                "dish": "Ramen",
                "score": 0.8,
                "text": "The ramen was amazing and spicy",
                "metadata": {
                    "type": "review",
                    "source": "ddgs",
                    "rating": 5
                }
            },
            {
                "dish": "Salad",
                "score": 0.3,
                "text": "Fresh garden salad",
                "metadata": {
                    "type": "menu_description",
                    "category": "Salads"
                }
            }
        ]
    )

    recommendations = engine.recommend_dishes("spicy noodles", top_k=2, use_llm=False)
    assert recommendations
    assert recommendations[0]["dish_name"] == "Ramen"
    assert recommendations[0]["metadata"]["spicy_level"] == 2


def test_get_dish_context():
    """Fetch dish context from vector store."""
    engine = RAGRecommendationEngine(gemini_api_key="dummy")
    engine.knowledge_base_built = True
    engine.vector_store = _FakeVectorStore(
        results=[
            {
                "dish": "Ramen",
                "score": 0.9,
                "text": "Spicy miso ramen with pork",
                "metadata": {
                    "type": "menu_description",
                    "category": "Noodles",
                    "price": 12.5,
                    "spicy_level": 2,
                    "allergens": ["gluten"],
                    "dietary_tags": ["dairy"]
                }
            },
            {
                "dish": "Ramen",
                "score": 0.8,
                "text": "The ramen was amazing and spicy",
                "metadata": {
                    "type": "review",
                    "source": "ddgs",
                    "rating": 5
                }
            },
            {
                "dish": "Ramen",
                "score": 0.7,
                "text": "Popular dish: Ramen.",
                "metadata": {
                    "type": "popularity",
                    "mention_count": 5
                }
            }
        ]
    )

    context = engine.get_dish_context("Ramen")
    assert context is not None
    assert context["menu_description"] is not None
    assert context["review_count"] == 1
    assert context["is_popular"] is True


def test_build_knowledge_base_stats():
    """Build knowledge base returns expected stats."""
    engine = RAGRecommendationEngine(gemini_api_key="dummy")
    engine.vector_store = _FakeVectorStore()

    async def _fake_collect_all_data(restaurant_name, location, place_id=None):
        return {
            "reviews": [
                {"text": "The ramen was incredible", "_source": "ddgs"}
            ],
            "images": [],
            "popular_dishes": [
                {"name": "Ramen", "mention_count": 3, "avg_sentiment": 0.8}
            ],
            "place_info": None,
            "sources": ["DuckDuckGo"],
            "metadata": {
                "successful_sources": 1,
                "failed_sources": []
            }
        }

    engine.aggregator.collect_all_data = _fake_collect_all_data

    parsed_menu = {
        "menu": [
            {
                "category": "Noodles",
                "items": [
                    {
                        "name": "Ramen",
                        "description": "Spicy miso ramen with pork",
                        "price": 12.5,
                        "spicy_level": 2,
                        "allergens": ["gluten"],
                        "dietary_tags": ["dairy"]
                    }
                ]
            }
        ]
    }

    stats = _run(
        engine.build_knowledge_base(
            restaurant_name="Test Ramen",
            location="Test City",
            parsed_menu=parsed_menu
        )
    )

    assert stats["total_documents"] == 3
    assert stats["menu_items"] == 1
    assert stats["review_mentions"] == 1
    assert stats["unique_dishes"] == 1
