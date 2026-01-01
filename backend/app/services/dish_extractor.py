"""Extract popular dishes from restaurant reviews using LLM."""

from google import genai
from google.genai import types
import json
import re
from collections import Counter
import logging

logger = logging.getLogger(__name__)

DISH_EXTRACTION_PROMPT = """Analyze these restaurant reviews and extract all dish names mentioned.

Return ONLY a JSON array of dish names, nothing else. No explanations, no markdown.

Rules:
- Extract complete dish names (e.g., "Classic Poutine", not just "Poutine")
- Normalize spelling and capitalization (e.g., "tonkatsu" → "Tonkatsu")
- Skip vague terms like "food", "meal", "dish", "order"
- Skip standalone adjectives (e.g., "delicious", "amazing") without dish names
- Include only actual menu items, not ingredients alone
- If a dish is mentioned multiple times, include it each time
- Keep dish names concise (e.g., "BBQ Pulled Pork Poutine" not "the amazing BBQ Pulled Pork Poutine")

Reviews:
{reviews}

Output format (ONLY this, nothing else):
["Dish Name 1", "Dish Name 2", "Dish Name 3", ...]
"""


def extract_popular_dishes(
    reviews: list[str],
    api_key: str,
    top_n: int = 10
) -> list[dict]:
    """Extract popular dishes from reviews using Gemini LLM.

    Args:
        reviews: List of review text strings.
        api_key: Gemini API key.
        top_n: Number of top popular dishes to return.

    Returns:
        List of popular dish dictionaries with name, mention_count, and avg_sentiment.
    """
    if not reviews:
        logger.warning("No reviews provided for dish extraction")
        return []

    # Combine reviews with numbering
    reviews_text = "\n\n".join([f"Review {i+1}: {r}" for i, r in enumerate(reviews)])

    logger.info(f"Extracting dishes from {len(reviews)} reviews")

    # Call Gemini to extract dishes
    try:
        client = genai.Client(api_key=api_key)
        prompt = DISH_EXTRACTION_PROMPT.format(reviews=reviews_text)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[types.Part.from_text(text=prompt)]
        )

        result_text = response.text.strip()
        logger.debug(f"Gemini response: {result_text[:200]}...")

        # Parse JSON array
        # Remove markdown if present
        result_text = re.sub(r'^```json\s*', '', result_text)
        result_text = re.sub(r'^```\s*', '', result_text)
        result_text = re.sub(r'\s*```$', '', result_text)

        # Extract array
        start = result_text.find("[")
        end = result_text.rfind("]")
        if start != -1 and end != -1:
            result_text = result_text[start:end+1]

        dishes = json.loads(result_text)
        logger.info(f"Extracted {len(dishes)} dish mentions")

        # Count occurrences
        dish_counts = Counter(dishes)

        # Return top N with counts
        popular = [
            {
                "name": dish,
                "mention_count": count,
                "avg_sentiment": 0.8,  # Placeholder - can enhance with sentiment analysis later
                "sample_reviews": []  # Can add sample reviews mentioning this dish
            }
            for dish, count in dish_counts.most_common(top_n)
        ]

        logger.info(f"Top {len(popular)} popular dishes identified")
        return popular

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse dish extraction JSON: {e}")
        logger.error(f"Raw response: {result_text}")
        return []
    except Exception as e:
        logger.error(f"Dish extraction failed: {e}")
        return []


def match_dish_to_menu(dish_name: str, menu_items: list[str], threshold: float = 0.7) -> str | None:
    """Match a popular dish to menu items using fuzzy matching.

    Args:
        dish_name: Popular dish name from reviews.
        menu_items: List of menu item names.
        threshold: Similarity threshold (0-1).

    Returns:
        Matched menu item name or None if no match found.
    """
    from difflib import SequenceMatcher

    best_match = None
    best_score = 0.0

    dish_lower = dish_name.lower()

    for menu_item in menu_items:
        menu_lower = menu_item.lower()

        # Exact match
        if dish_lower == menu_lower:
            return menu_item

        # Substring match
        if dish_lower in menu_lower or menu_lower in dish_lower:
            score = 0.9
        else:
            # Fuzzy match
            score = SequenceMatcher(None, dish_lower, menu_lower).ratio()

        if score > best_score:
            best_score = score
            best_match = menu_item

    if best_score >= threshold:
        logger.info(f"Matched '{dish_name}' to '{best_match}' (score: {best_score:.2f})")
        return best_match

    return None
