"""Menu image parsing using Gemini 2.5 Vision API.

Migrated from rag_gemini.py with improvements for production use.
"""

import json
from google import genai
from google.genai import types
import requests

from app.models.menu import ParsedMenu


PROMPT = """
You are an expert at understanding restaurant menus.

Analyze the menu in this image and extract a structured representation of all the dishes.

Your tasks:
1. Read all visible text from the image (OCR).
2. Identify and group the content into categories such as "Appetizers", "Breakfast", "Desserts", "Drinks", etc.
3. For each dish, extract:
   - name: the dish name
   - price: the numeric price if visible
   - description: short ingredient or preparation text under the dish (if present)
4. Preserve the order from top to bottom and left to right.
5. Skip any irrelevant text (like phone numbers, URLs, social media handles, "catering available", etc.)

Return a **valid JSON** object with the following structure:
{
  "menu": [
    {
      "category": "Category Name",
      "items": [
        {"name": "Dish Name", "price": 12.5, "description": "Optional description"},
        ...
      ]
    }
  ]
}

Only output valid JSON, no explanations.
If the menu text appears without punctuation but looks like a list of ingredients or items, especially at the end of lines,
insert commas appropriately to separate distinct food items (e.g., "SAUSAGE GRAVY CHEESE CURDS" → "Sausage Gravy, Cheese Curds").
Normalize capitalization while keeping names readable.
"""


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
    """Safely parse JSON from model output.

    Args:
        text: Raw text output from the model.

    Returns:
        Parsed JSON as a dictionary.

    Raises:
        ValueError: If JSON parsing fails.
    """
    json_str = text.strip()

    # Try to extract JSON object if surrounded by markdown or text
    start = json_str.find("{")
    end = json_str.rfind("}")
    if start != -1 and end != -1:
        json_str = json_str[start:end+1]

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        msg = f"Failed to parse JSON from model output: {e}"
        raise ValueError(msg) from e


def parse_menu_image(
    image_source: str | bytes,
    api_key: str,
    model_name: str = "gemini-2.5-flash"
) -> ParsedMenu:
    """Parse a menu image into structured data using Gemini Vision API.

    Args:
        image_source: Image URL, file path, or raw bytes.
        api_key: Gemini API key.
        model_name: Gemini model to use.

    Returns:
        Parsed menu structure with categories and items.

    Raises:
        ValueError: If the API response cannot be parsed as valid menu JSON.
    """
    image_part = load_image_part(image_source)

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=model_name,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=PROMPT),
                    image_part
                ]
            )
        ]
    )

    result_text = response.text.strip()
    parsed_json = safe_json_parse(result_text)

    return ParsedMenu(**parsed_json)
