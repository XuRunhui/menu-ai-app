"""Unit tests for TasteTexturePredictor."""

import asyncio
import os
import sys

import pytest

pytest.importorskip("openai")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.recommendation.taste_texture_predictor import TasteTexturePredictor  # noqa: E402


class _FakeClient:
    def __init__(self, text: str):
        self._text = text

    def generate(self, prompt: str, **kwargs):
        return self._text


def _run(coro):
    return asyncio.run(coro)


def test_parse_prediction_with_markdown():
    """Parse JSON from markdown code blocks."""
    predictor = TasteTexturePredictor(api_key="")
    response_text = """```json
{
  "tastes": ["spicy", "umami"],
  "textures": ["soft", "silky"],
  "flavor_profile": "Rich and complex with moderate heat",
  "confidence": 0.72,
  "round": 1
}
```"""
    result = predictor._parse_prediction(response_text, round_number=1)
    assert result is not None
    assert "spicy" in result["tastes"]
    assert "silky" in result["textures"]


def test_predict_round1_parses_response():
    """Round 1 prediction uses LLM response when parseable."""
    predictor = TasteTexturePredictor(api_key="")
    predictor.llm_client = _FakeClient(
        """{
  "tastes": ["spicy", "umami"],
  "textures": ["soft"],
  "flavor_profile": "Spicy and savory",
  "confidence": 0.7,
  "round": 1
}"""
    )

    result = _run(predictor.predict_round1("Spicy Ramen", "Hot noodles in spicy broth"))
    assert result["round"] == 1
    assert "spicy" in result["tastes"]


def test_predict_round2_improves_confidence():
    """Round 2 prediction improves or equals confidence."""
    predictor = TasteTexturePredictor(api_key="")
    predictor.llm_client = _FakeClient(
        """{
  "tastes": ["spicy", "umami", "rich"],
  "textures": ["soft", "tender"],
  "flavor_profile": "Rich umami broth",
  "confidence": 0.85,
  "round": 2,
  "changes_from_round1": ["Added 'rich' based on reviews"]
}"""
    )

    round1 = {
        "tastes": ["spicy", "umami"],
        "textures": ["soft"],
        "flavor_profile": "Spicy and savory",
        "confidence": 0.65,
        "round": 1
    }

    result = _run(
        predictor.predict_round2(
            "Spicy Ramen",
            "Hot noodles in spicy broth",
            ["Broth is rich and noodles are tender"],
            round1
        )
    )
    assert result["round"] == 2
    assert result["confidence"] >= round1["confidence"]


def test_predict_invalid_response_falls_back():
    """Invalid LLM response returns fallback prediction."""
    predictor = TasteTexturePredictor(api_key="")
    predictor.llm_client = _FakeClient("not valid json")

    result = _run(predictor.predict_round1("Spicy Ramen", "Hot noodles in spicy broth"))
    assert result["round"] == 1
    assert result["tastes"]
    assert result["textures"]
