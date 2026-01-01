"""Menu image parsing using Gemini 2.5 Vision API with multilingual support.

Supports automatic language detection and translation to any target language.
"""

import json
from google import genai
from google.genai import types
import requests

from app.models.menu import ParsedMenu


def build_multilingual_prompt(target_language: str | None = None) -> str:
    """Build a prompt for multilingual menu parsing with optional translation.

    Args:
        target_language: Target language for translation (e.g., "English", "Chinese", "Spanish").
                        If None, only parse without translation.

    Returns:
        Formatted prompt string for Gemini.
    """
    base_prompt = """You are an expert at understanding restaurant menus in any language.

Analyze the menu in this image and extract a structured representation of all the dishes.

Your tasks:
1. Detect the language of the menu text automatically
2. Read all visible text from the image (OCR) in the original language
3. Identify and group the content into categories
4. For each dish, extract:
   - name: the dish name in original language
   - price: NUMERIC price ONLY (e.g., 12.5, 800, 45.99)
   - price_original: the EXACT price text from image (e.g., "八百円", "$12.50", "¥800")
   - currency: currency symbol or code (e.g., "$", "¥", "€", "USD", "JPY")
   - description: ingredient or preparation text in original language (if present)
5. Preserve the order from top to bottom and left to right
6. Skip irrelevant text (phone numbers, URLs, social media, etc.)

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
          "description": "Description in original language","""

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


def load_image_part(image_source: str | bytes) -> types.Part:
    """Load an image from URL, file path, or bytes into a Gemini Part.

    Args:
        image_source: Either a URL (str starting with http), a file path (str), or raw bytes.

    Returns:
        A Gemini Part object containing the image data.
    """
    if isinstance(image_source, bytes):
        image_bytes = image_source
    elif isinstance(image_source, str) and image_source.startswith("http"):
        image_bytes = requests.get(image_source).content
    else:
        with open(image_source, "rb") as f:
            image_bytes = f.read()

    return types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")


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
    model_name: str = "gemini-2.5-flash"
) -> ParsedMenu:
    """Parse a menu image into structured data with optional translation.

    Args:
        image_source: Image URL, file path, or raw bytes.
        api_key: Gemini API key.
        target_language: Target language for translation (e.g., "English", "Chinese").
                        If None, only parse without translation.
        model_name: Gemini model to use.

    Returns:
        Parsed menu structure with categories and items in original and translated languages.

    Raises:
        ValueError: If the API response cannot be parsed as valid menu JSON.
    """
    image_part = load_image_part(image_source)
    prompt = build_multilingual_prompt(target_language)

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=model_name,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                    image_part
                ]
            )
        ]
    )

    result_text = response.text.strip()

    # Log raw response for debugging (first 1000 chars)
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"Gemini raw response (first 1000 chars): {result_text[:1000]}")

    parsed_json = safe_json_parse(result_text)

    return ParsedMenu(**parsed_json)
