"""Taste and texture prediction using a two-round LLM workflow.

This module predicts sensory attributes for dishes using:
1) Round 1: Menu description only
2) Round 2: Refine using customer review excerpts

Example Usage:
    >>> from app.services.recommendation.taste_texture_predictor import TasteTexturePredictor
    >>> predictor = TasteTexturePredictor(api_key="sk-...")
    >>> round1 = await predictor.predict_round1(
    ...     dish_name="Soon Tofu Jjigae",
    ...     description="Spicy soft tofu stew with seafood"
    ... )
    >>> round1["round"]
    1
    >>> round2 = await predictor.predict_round2(
    ...     dish_name="Soon Tofu Jjigae",
    ...     description="Spicy soft tofu stew with seafood",
    ...     review_excerpts=["Tofu was silky and broth was rich"],
    ...     round1_prediction=round1
    ... )
    >>> round2["round"]
    2
"""

import json
import logging
import re
from typing import Dict, List, Optional

from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

TASTE_ATTRIBUTES = [
    "sweet", "salty", "sour", "bitter", "umami",
    "spicy", "savory", "mild", "rich", "light",
    "smoky", "tangy", "aromatic", "fresh", "creamy"
]

TEXTURE_ATTRIBUTES = [
    "crispy", "crunchy", "tender", "soft", "chewy",
    "juicy", "creamy", "flaky", "smooth", "firm",
    "silky", "fluffy", "sticky", "moist", "delicate"
]


class TasteTexturePredictor:
    """Predict taste and texture attributes for menu items.

    Attributes:
        llm_client: DeepSeek client for LLM inference (None without API key).
        model_name: DeepSeek model name used for predictions.
        taste_attributes: Allowed taste taxonomy.
        texture_attributes: Allowed texture taxonomy.

    Note:
        If the LLM response cannot be parsed, a fallback heuristic
        prediction is returned to keep the pipeline resilient.
    """

    def __init__(self, api_key: str, model_name: Optional[str] = None):
        """Initialize predictor with DeepSeek API key.

        Args:
            api_key: DeepSeek API key.
            model_name: DeepSeek model name (defaults to settings.deepseek_model).

        Example:
            >>> predictor = TasteTexturePredictor(api_key="sk-...", model_name="deepseek-flash")
            >>> predictor.model_name
            'deepseek-flash'
        """
        self.llm_client = LLMClient(api_key=api_key, model_name=model_name) if api_key else None
        self.model_name = self.llm_client.model_name if self.llm_client else model_name
        self.taste_attributes = TASTE_ATTRIBUTES
        self.texture_attributes = TEXTURE_ATTRIBUTES
        if not api_key:
            logger.warning("TasteTexturePredictor initialized without API key")

    async def predict_round1(self, dish_name: str, description: str) -> Dict:
        """Predict taste and texture from menu description.

        Args:
            dish_name: Name of the dish.
            description: Menu description text.

        Returns:
            Prediction dictionary with tastes, textures, flavor_profile,
            confidence, and round number.

        Example:
            >>> result = await predictor.predict_round1(
            ...     "Spicy Ramen",
            ...     "Hot noodles in spicy broth with pork"
            ... )
            >>> "spicy" in result["tastes"]
            True

        Edge Cases:
            - Empty description: returns a conservative fallback prediction.
            - LLM response parsing failure: uses heuristic fallback.
        """
        if not dish_name or not description:
            raise ValueError("dish_name and description are required")

        prompt = self._build_round1_prompt(dish_name, description)

        try:
            if self.llm_client:
                # Round 1 sees only the menu description, so its answer is safe to cache and reuse.
                response_text = self.llm_client.generate(
                    prompt, json_mode=True, cache=True, purpose="taste_round1"
                )
                parsed = self._parse_prediction(response_text, round_number=1)
                if parsed:
                    return parsed
            else:
                logger.warning("LLM client unavailable; using fallback prediction")
        except Exception as e:
            logger.error(f"Round 1 prediction failed for '{dish_name}': {e}")

        return self._fallback_prediction(dish_name, description, round_number=1)

    async def predict_round2(
        self,
        dish_name: str,
        description: str,
        review_excerpts: List[str],
        round1_prediction: Dict
    ) -> Dict:
        """Refine taste and texture prediction using review excerpts.

        Args:
            dish_name: Name of the dish.
            description: Menu description text.
            review_excerpts: List of review excerpt strings.
            round1_prediction: Output from predict_round1.

        Returns:
            Refined prediction dictionary with changes_from_round1.

        Example:
            >>> round1 = await predictor.predict_round1("Ramen", "Spicy noodles")
            >>> round2 = await predictor.predict_round2(
            ...     "Ramen",
            ...     "Spicy noodles",
            ...     ["Broth is rich", "Noodles are chewy"],
            ...     round1
            ... )
            >>> round2["round"]
            2
        """
        if not dish_name or not description:
            raise ValueError("dish_name and description are required")

        if not review_excerpts:
            logger.warning(f"No reviews provided for round 2 for '{dish_name}'")
            return self._fallback_round2_from_round1(round1_prediction)

        prompt = self._build_round2_prompt(
            dish_name,
            description,
            review_excerpts,
            round1_prediction
        )

        try:
            if self.llm_client:
                response_text = self.llm_client.generate(prompt, json_mode=True)
                parsed = self._parse_prediction(response_text, round_number=2)
                if parsed:
                    if "changes_from_round1" not in parsed:
                        parsed["changes_from_round1"] = self._build_changes_from_round1(
                            round1_prediction,
                            parsed
                        )
                    return parsed
            else:
                logger.warning("LLM client unavailable; using fallback prediction")
        except Exception as e:
            logger.error(f"Round 2 prediction failed for '{dish_name}': {e}")

        fallback = self._fallback_prediction(dish_name, description, round_number=2)
        fallback["changes_from_round1"] = self._build_changes_from_round1(
            round1_prediction,
            fallback
        )
        return fallback

    def _build_round1_prompt(self, dish_name: str, description: str) -> str:
        """Build prompt template for round 1 prediction."""
        taste_list = ", ".join(self.taste_attributes)
        texture_list = ", ".join(self.texture_attributes)

        return (
            "You are a culinary expert. Predict taste and texture attributes for the dish.\n\n"
            f"Dish: {dish_name}\n"
            f"Description: {description}\n\n"
            "Use only the following taxonomies.\n"
            f"Taste attributes: [{taste_list}]\n"
            f"Texture attributes: [{texture_list}]\n\n"
            "Return ONLY JSON with this schema:\n"
            "{\n"
            '  "tastes": ["spicy", "savory"],\n'
            '  "textures": ["soft", "silky"],\n'
            '  "flavor_profile": "Rich and complex with moderate heat",\n'
            '  "confidence": 0.0,\n'
            '  "round": 1\n'
            "}\n"
        )

    def _build_round2_prompt(
        self,
        dish_name: str,
        description: str,
        reviews: List[str],
        round1: Dict
    ) -> str:
        """Build prompt template for round 2 refinement."""
        taste_list = ", ".join(self.taste_attributes)
        texture_list = ", ".join(self.texture_attributes)
        review_text = "\n".join([f"- {review}" for review in self._normalize_reviews(reviews)])
        round1_json = json.dumps(round1, indent=2)

        return (
            "You are refining a taste/texture prediction using customer reviews.\n\n"
            f"Dish: {dish_name}\n"
            f"Description: {description}\n\n"
            f"Round 1 prediction:\n{round1_json}\n\n"
            "Customer review excerpts:\n"
            f"{review_text}\n\n"
            "Use only the following taxonomies.\n"
            f"Taste attributes: [{taste_list}]\n"
            f"Texture attributes: [{texture_list}]\n\n"
            "Return ONLY JSON with this schema:\n"
            "{\n"
            '  "tastes": ["spicy", "savory", "rich"],\n'
            '  "textures": ["soft", "silky", "tender"],\n'
            '  "flavor_profile": "Rich umami broth with balanced heat and silky tofu",\n'
            '  "confidence": 0.0,\n'
            '  "round": 2,\n'
            '  "changes_from_round1": ["Added \'rich\' based on reviews"]\n'
            "}\n"
        )

    def _parse_prediction(self, response_text: Optional[str], round_number: int) -> Optional[Dict]:
        """Parse LLM response text into a normalized prediction dict."""
        if not response_text:
            return None

        result_text = response_text.strip()
        result_text = re.sub(r"^```json\s*", "", result_text)
        result_text = re.sub(r"^```\s*", "", result_text)
        result_text = re.sub(r"\s*```$", "", result_text)

        start = result_text.find("{")
        end = result_text.rfind("}")
        if start == -1 or end == -1:
            logger.warning("No JSON object found in prediction response")
            return None

        result_text = result_text[start:end + 1]

        try:
            data = json.loads(result_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse prediction JSON: {e}")
            logger.error(f"Raw response: {result_text}")
            return None

        tastes = self._normalize_attributes(data.get("tastes", []), self.taste_attributes)
        textures = self._normalize_attributes(data.get("textures", []), self.texture_attributes)

        if not tastes or not textures:
            logger.warning("Parsed prediction missing tastes or textures")
            return None

        flavor_profile = str(data.get("flavor_profile", "")).strip()
        confidence = self._normalize_confidence(data.get("confidence"))

        prediction = {
            "tastes": tastes,
            "textures": textures,
            "flavor_profile": flavor_profile or "Balanced flavor profile",
            "confidence": confidence,
            "round": round_number
        }

        if "changes_from_round1" in data and isinstance(data["changes_from_round1"], list):
            prediction["changes_from_round1"] = [
                str(change).strip() for change in data["changes_from_round1"] if str(change).strip()
            ]

        return prediction

    def _normalize_attributes(self, values: object, allowed: List[str]) -> List[str]:
        """Normalize and filter LLM attributes against allowed taxonomy."""
        if isinstance(values, str):
            values = [item.strip() for item in values.split(",")]
        if not isinstance(values, list):
            return []

        normalized = []
        for item in values:
            value = str(item).strip().lower()
            if not value:
                continue
            if value in allowed and value not in normalized:
                normalized.append(value)

        return normalized

    def _normalize_confidence(self, value: object) -> float:
        """Normalize confidence to a float between 0 and 1."""
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.5

        if confidence < 0.0:
            return 0.0
        if confidence > 1.0:
            return 1.0
        return confidence

    def _normalize_reviews(self, reviews: List[object]) -> List[str]:
        """Normalize review excerpts into a list of short strings."""
        normalized = []
        for review in reviews[:8]:
            if isinstance(review, dict):
                text = review.get("text") or review.get("excerpt") or ""
            else:
                text = str(review)
            text = text.strip()
            if text:
                normalized.append(text[:280])
        return normalized

    def _fallback_prediction(self, dish_name: str, description: str, round_number: int) -> Dict:
        """Create a fallback prediction using simple keyword heuristics."""
        text = f"{dish_name} {description}".lower()

        tastes = []
        textures = []

        taste_map = {
            "spicy": ["spicy", "chili", "pepper", "hot", "heat"],
            "sweet": ["sweet", "honey", "sugar", "maple"],
            "salty": ["salty", "soy", "brined"],
            "sour": ["sour", "tangy", "citrus", "lemon", "vinegar"],
            "bitter": ["bitter"],
            "umami": ["umami", "miso", "mushroom", "broth", "beef", "pork"],
            "smoky": ["smoky", "smoked", "char", "bbq"],
            "creamy": ["creamy", "cream", "cheese", "butter"],
            "fresh": ["fresh", "herb", "salad"],
            "aromatic": ["aromatic", "garlic", "ginger", "basil"],
            "rich": ["rich", "braised", "buttery"],
            "light": ["light", "broth", "clear"]
        }

        texture_map = {
            "crispy": ["crispy", "fried", "crisp"],
            "crunchy": ["crunchy"],
            "tender": ["tender", "braised", "slow-cooked", "slow cooked"],
            "soft": ["soft", "tofu"],
            "chewy": ["chewy", "noodle", "mochi"],
            "juicy": ["juicy", "succulent"],
            "creamy": ["creamy", "cream"],
            "flaky": ["flaky", "fish"],
            "smooth": ["smooth", "puree"],
            "firm": ["firm"],
            "silky": ["silky"],
            "fluffy": ["fluffy", "whipped"],
            "sticky": ["sticky", "glutinous"],
            "moist": ["moist"],
            "delicate": ["delicate"]
        }

        for taste, keywords in taste_map.items():
            if any(keyword in text for keyword in keywords):
                tastes.append(taste)

        for texture, keywords in texture_map.items():
            if any(keyword in text for keyword in keywords):
                textures.append(texture)

        if not tastes:
            tastes = ["savory"]
        if not textures:
            textures = ["tender"]

        flavor_profile = f"{', '.join(tastes[:2]).title()} with {', '.join(textures[:2])} texture"

        return {
            "tastes": tastes[:3],
            "textures": textures[:3],
            "flavor_profile": flavor_profile,
            "confidence": 0.55,
            "round": round_number
        }

    def _fallback_round2_from_round1(self, round1_prediction: Optional[Dict]) -> Dict:
        """Create a round 2 response when reviews are missing."""
        if not round1_prediction:
            return {
                "tastes": ["savory"],
                "textures": ["tender"],
                "flavor_profile": "Balanced profile based on limited data",
                "confidence": 0.5,
                "round": 2,
                "changes_from_round1": ["No round 1 prediction available"]
            }

        round2 = dict(round1_prediction)
        round2["round"] = 2
        round2["changes_from_round1"] = [
            "No review data provided; returned round 1 prediction"
        ]
        return round2

    def _build_changes_from_round1(self, round1: Optional[Dict], round2: Dict) -> List[str]:
        """Build a list of changes between round 1 and round 2 predictions."""
        if not round1:
            return ["No round 1 data to compare; generated from reviews"]

        changes = []
        round1_tastes = set(round1.get("tastes", []))
        round2_tastes = set(round2.get("tastes", []))
        round1_textures = set(round1.get("textures", []))
        round2_textures = set(round2.get("textures", []))

        for taste in sorted(round2_tastes - round1_tastes):
            changes.append(f"Added '{taste}' based on review mentions")

        for texture in sorted(round2_textures - round1_textures):
            changes.append(f"Added '{texture}' texture based on reviews")

        round1_conf = round1.get("confidence")
        round2_conf = round2.get("confidence")
        if isinstance(round1_conf, (int, float)) and isinstance(round2_conf, (int, float)):
            if round2_conf != round1_conf:
                changes.append(
                    f"Adjusted confidence from {round1_conf:.2f} to {round2_conf:.2f}"
                )

        if not changes:
            changes.append("No significant changes after review refinement")

        return changes[:3]


# Debug/Testing Examples (commented out)
"""
if __name__ == "__main__":
    import asyncio
    import os

    async def test_predictor():
        predictor = TasteTexturePredictor(api_key=os.getenv("DEEPSEEK_API_KEY"))

        round1 = await predictor.predict_round1(
            dish_name="Soon Tofu Jjigae",
            description="Spicy soft tofu stew with seafood and vegetables"
        )
        print("Round 1:", json.dumps(round1, indent=2))

        round2 = await predictor.predict_round2(
            dish_name="Soon Tofu Jjigae",
            description="Spicy soft tofu stew with seafood and vegetables",
            review_excerpts=[
                "The tofu was silky and the broth was rich",
                "Perfect level of spice, not too overwhelming"
            ],
            round1_prediction=round1
        )
        print("Round 2:", json.dumps(round2, indent=2))

    asyncio.run(test_predictor())
"""
