"""Built-in results for the bundled sample menu (frontend/public/sample-menu.png).

Loaded at every startup so "Try a sample menu" is instant and its links keep working on a fresh
server, e.g. a Cloud Run instance that just woke up with an empty cache database.

Rebuild after changing the sample image, the parse prompt, or the combo pipeline (uses DeepSeek):
    cd backend && python -m app.demo.sample_seed build
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
from pathlib import Path

from app.core.config import settings
from app.services import cache_service

logger = logging.getLogger(__name__)

SEED_PATH = Path(__file__).with_name("sample_seed.json")
SAMPLE_IMAGE = Path(__file__).resolve().parents[3] / "frontend" / "public" / "sample-menu.png"
SAMPLE_RESTAURANT = "The Kroft"  # what the "Try a sample menu" button fills in


def load_seed(path: Path = SEED_PATH) -> bool:
    """Put the sample menu and its combos into the shared caches. Returns False if there is no seed."""
    from app.api.v1.endpoints.knowledge import combo_cache_key
    from app.models.knowledge import ComboRequest

    if not path.exists():
        return False
    seed = json.loads(path.read_text(encoding="utf-8"))
    menu = seed["parsed_menu"]
    cache_service.seed_menu_parse(
        seed["menu_id"], seed["image_sha256"], settings.deepseek_model, seed["restaurant_name"],
        menu.get("detected_language"), sum(len(c["items"]) for c in menu["menu"]), menu,
    )
    key = combo_cache_key(ComboRequest(**seed["combo_request"]))
    if cache_service.get_llm_response(key) is None:
        cache_service.set_llm_response(key, settings.deepseek_model, "combo_response", json.dumps(seed["combo_response"]))
    logger.info("Loaded demo seed for the sample menu (menu_id=%s)", seed["menu_id"])
    return True


def build_seed(path: Path = SEED_PATH) -> dict:
    """Parse the sample menu and compute its combos with the real pipeline, then write the seed file."""
    from app.api.v1.endpoints.knowledge import compute_combos
    from app.models.knowledge import ComboRequest
    from app.services.vision_parser import parse_menu_image

    if not settings.deepseek_api_key:
        sys.exit("DEEPSEEK_API_KEY is not set")

    image = SAMPLE_IMAGE.read_bytes()
    image_sha256 = hashlib.sha256(image).hexdigest()
    parsed = parse_menu_image(image, api_key=settings.deepseek_api_key)

    # Must match exactly what the frontend's Combo tab sends for this menu.
    request = ComboRequest(
        dishes=[{"name": item.name, "description": item.description, "category": category.category}
                for category in parsed.menu for item in category.items],
        max_combos=3,
        restaurant_name=SAMPLE_RESTAURANT,
    )
    response = compute_combos(request)

    seed = {
        "image_sha256": image_sha256,
        "menu_id": image_sha256[:32],
        "restaurant_name": SAMPLE_RESTAURANT,
        "parsed_menu": parsed.model_dump(exclude={"menu_id"}),
        "combo_request": request.model_dump(),
        "combo_response": response.model_dump(),
    }
    path.write_text(json.dumps(seed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return seed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if sys.argv[1:] != ["build"]:
        sys.exit("Usage: python -m app.demo.sample_seed build")
    from app.db.session import init_db

    init_db()
    result = build_seed()
    print(f"Wrote {SEED_PATH} ({sum(len(c['items']) for c in result['parsed_menu']['menu'])} dishes, "
          f"{len(result['combo_response']['combos'])} combos)")
