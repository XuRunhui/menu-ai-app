"""Menu image parsing using the DeepSeek multimodal API with multilingual support.

Supports automatic language detection and translation to any target language.
"""

import json
import logging

import requests

from app.models.menu import ParsedMenu
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


def build_multilingual_prompt(target_language: str | None = None, medium: str = "image") -> str:
    """Build a prompt for multilingual menu parsing with optional translation.

    Args:
        target_language: Target language for translation (e.g., "English", "Chinese", "Spanish").
                        If None, only parse without translation.
        medium: "image" for a photo of a menu, "text" for text taken from a web page or PDF. Both
            produce the same JSON, so menus from either can be combined.

    Returns:
        Formatted prompt string for the LLM.
    """
    if medium == "text":
        opening = """Below is text taken from a restaurant's web page or PDF. Extract a structured \
representation of the dishes on its menu.

The page may also contain navigation links, opening hours, addresses, reviews and other text that \
is not the menu: ignore all of it. Use only dishes that actually appear in the text; never add \
dishes the page doesn't list. If the text contains no menu at all, return "menu": []. The text may \
be one part of a longer menu, starting or ending mid-section: extract what is there.

When a name, category or description is already written in the target language, set its \
*_translated field to null rather than repeating it.

Your tasks:
1. Detect the language of the menu text automatically
2. Find every dish in the text, keeping its name in the original language"""
    else:
        opening = """Analyze the menu in this image and extract a structured representation of all the dishes.

Your tasks:
1. Detect the language of the menu text automatically
2. Read all visible text from the image (OCR) in the original language"""

    base_prompt = """You are an expert at understanding restaurant menus in any language.

""" + opening + """
3. Identify and group the content into categories
4. For each dish, extract:
   - name: the dish name in original language
   - price: NUMERIC price ONLY (e.g., 12.5, 800, 45.99)
   - price_original: the EXACT price text from image (e.g., "八百円", "$12.50", "¥800")
   - currency: currency symbol or code (e.g., "$", "¥", "€", "USD", "JPY")
   - description: ingredient or preparation text in original language (if present)
5. Detect SYMBOLS and INDICATORS next to dishes:
   - spicy_level: Number of chili peppers 🌶️ or asterisks * (0-5, null if not specified)
   - allergens: List from ["nuts", "peanuts", "dairy", "milk", "gluten", "wheat", "shellfish", "fish", "soy", "eggs", "sesame"]
     * Look for symbols: 🥜 (nuts), 🥛 (dairy), 🌾 (gluten), 🦐 (shellfish), 🥚 (eggs)
     * Look for text: "Contains nuts", "Gluten-free", "Dairy-free"
   - dietary_tags: List from ["vegetarian", "vegan", "gluten-free", "halal", "kosher", "organic"]
     * Look for symbols: (V) = vegetarian, (VG) = vegan, (GF) = gluten-free
     * Look for text markers or badges
6. Preserve the order from top to bottom and left to right
7. Skip irrelevant text (phone numbers, URLs, social media, etc.)

PRICE HANDLING RULES:
- If price is in words/native language (e.g., "八百円"=800yen, "十块"=10yuan), convert to number
- Always preserve EXACT original price text in price_original
- If price is unclear or handwritten and you can't read it, set price to null but keep price_original
- Extract currency symbol (¥, $, €, etc.) separately
- Examples:
  * "八百円" → price: 800, price_original: "八百円", currency: "¥"
  * "$12.50" → price: 12.5, price_original: "$12.50", currency: "$"
  * "market price" → price: null, price_original: "market price", currency: null"""

    if target_language:
        translation_instruction = f"""
7. Translate ALL text to {target_language}:
   - category_translated: Translate category name to {target_language}
   - name_translated: Translate dish name to {target_language}
   - description_translated: Translate description to {target_language}
   Keep translations natural and culturally appropriate."""
    else:
        translation_instruction = ""

    json_structure = """

Return a **valid JSON** object with this EXACT structure:
{
  "detected_language": "Language Name (e.g., Japanese, Chinese, Korean, English, etc.)",
  "target_language": """ + (f'"{target_language}"' if target_language else 'null') + """,
  "menu": [
    {
      "category": "Category in original language","""

    if target_language:
        json_structure += """
      "category_translated": "Category in """ + target_language + """","""

    json_structure += """
      "items": [
        {
          "name": "Dish name in original language","""

    if target_language:
        json_structure += """
          "name_translated": "Dish name in """ + target_language + """","""

    json_structure += """
          "price": 12.5,
          "price_original": "¥1250",
          "currency": "¥",
          "description": "Description in original language",
          "spicy_level": 3,
          "allergens": ["shellfish", "soy"],
          "dietary_tags": ["gluten-free"],"""

    if target_language:
        json_structure += """
          "description_translated": "Description in """ + target_language + """"""

    json_structure += """
        }
      ]
    }
  ]
}

CRITICAL JSON FORMATTING RULES:
- Output ONLY valid JSON, nothing else (no markdown, no explanations, no ```json blocks)
- NO trailing commas before ] or }
- Use double quotes for all strings, not single quotes
- Escape special characters in strings (quotes, backslashes, newlines)
- If description contains quotes, escape them: \\"
- Ensure all brackets and braces are balanced
- Test your JSON is valid before returning

OTHER RULES:
- Preserve original text exactly as it appears
- Normalize capitalization while keeping names readable
- For Asian languages (Chinese, Japanese, Korean), preserve character accuracy
- Detect language based on the actual text in the image, not assumptions
"""
    return base_prompt + translation_instruction + json_structure


def load_image_bytes(image_source: str | bytes) -> bytes:
    """Load an image from URL, file path, or bytes.

    Args:
        image_source: Either a URL (str starting with http), a file path (str), or raw bytes.

    Returns:
        Raw image bytes.
    """
    if isinstance(image_source, bytes):
        return image_source
    if isinstance(image_source, str) and image_source.startswith("http"):
        return requests.get(image_source, timeout=30).content
    with open(image_source, "rb") as f:
        return f.read()


def safe_json_parse(text: str) -> dict:
    """Safely parse JSON from model output with error recovery.

    Args:
        text: Raw text output from the model.

    Returns:
        Parsed JSON as a dictionary.

    Raises:
        ValueError: If JSON parsing fails after all recovery attempts.
    """
    import re

    json_str = text.strip()

    # Remove markdown code blocks
    json_str = re.sub(r'^```json\s*', '', json_str)
    json_str = re.sub(r'^```\s*', '', json_str)
    json_str = re.sub(r'\s*```$', '', json_str)

    # Try to extract JSON object if surrounded by text
    start = json_str.find("{")
    end = json_str.rfind("}")
    if start != -1 and end != -1:
        json_str = json_str[start:end+1]

    # Try parsing as-is first
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # Try fixing common issues: trailing commas
    # Remove trailing commas before } or ]
    json_str_fixed = re.sub(r',(\s*[}\]])', r'\1', json_str)

    try:
        return json.loads(json_str_fixed)
    except json.JSONDecodeError:
        pass

    # Try to fix missing commas between objects (common with descriptions)
    # This is more aggressive and might not always work
    json_str_fixed = re.sub(r'"\s*\n\s*"', '",\n"', json_str_fixed)

    try:
        return json.loads(json_str_fixed)
    except json.JSONDecodeError as e:
        # Log the actual JSON for debugging
        msg = f"Failed to parse JSON from model output: {e}\nJSON preview: {json_str[:500]}..."
        raise ValueError(msg) from e


def parse_menu_image(
    image_source: str | bytes,
    api_key: str,
    target_language: str | None = None,
    model_name: str | None = None,
    cache: bool = False,
) -> ParsedMenu:
    """Parse a menu image into structured data with optional translation.

    Args:
        image_source: Image URL, file path, or raw bytes.
        api_key: DeepSeek API key.
        target_language: Target language for translation (e.g., "English", "Chinese").
                        If None, only parse without translation.
        model_name: DeepSeek model to use (defaults to settings.deepseek_model).
        cache: Reuse the answer for the same image bytes and language. Uploads have their own
               cache by image hash (MenuParseCache); the website reader turns this on, since a
               restaurant's menu images and PDF pages are the same on every visit.

    Returns:
        Parsed menu structure with categories and items in original and translated languages.

    Raises:
        ValueError: If the API response cannot be parsed as valid menu JSON.
    """
    image_bytes = load_image_bytes(image_source)
    prompt = build_multilingual_prompt(target_language)

    client = LLMClient(api_key=api_key, model_name=model_name)
    result_text = client.generate(prompt, image_bytes=image_bytes, json_mode=True,
                                  cache=cache, purpose="menu_image")

    logger.debug(f"LLM raw response (first 1000 chars): {result_text[:1000]}")

    parsed_json = safe_json_parse(result_text)

    return ParsedMenu(**parsed_json)


# Enough for a long menu page; beyond this is almost always boilerplate, and the reply must fit
# within the model's output budget.
MAX_MENU_TEXT_CHARS = 24_000


# One piece of a long menu can run to a few thousand output tokens; the app-wide default cap (8,192)
# was cutting big menus off mid-JSON. deepseek-flash allows far more.
MENU_TEXT_MAX_TOKENS = 16_000


def parse_menu_text(
    text: str,
    api_key: str,
    target_language: str | None = None,
    model_name: str | None = None,
) -> ParsedMenu:
    """Parse menu text (from a restaurant's website or a PDF) into the same shape as a photo.

    Cached by content: the text comes from the restaurant's own site rather than from Google, so
    the same page is only ever paid for once.

    Raises:
        ValueError: If the model's reply is not valid menu JSON.
    """
    prompt = build_multilingual_prompt(target_language, medium="text")
    prompt += "\n\nPAGE TEXT:\n" + text[:MAX_MENU_TEXT_CHARS]

    client = LLMClient(api_key=api_key, model_name=model_name)
    result_text = client.generate(prompt, json_mode=True, cache=True, purpose="website_menu",
                                  max_tokens=MENU_TEXT_MAX_TOKENS)
    return ParsedMenu(**safe_json_parse(result_text))
