"""Dish image API endpoint — search, cache, and serve per-dish images."""

import logging

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel
from typing import Optional

from app.core.rate_limit import enforce_dish_image_limit
from app.services import cache_service
from app.services.dish_image_service import get_dish_image_service

router = APIRouter()
logger = logging.getLogger(__name__)


class DishImageResponse(BaseModel):
    """Response shape for the dish image endpoint."""

    image_url: Optional[str] = None
    cached: bool = False
    # Credit line for photos whose license requires it (e.g. Wikimedia Commons).
    attribution: str = ""
    source: str = ""


def _build_image_url(request: Request, filename: str) -> str:
    """Construct the full URL to the locally-served dish image."""
    base = str(request.base_url).rstrip("/")
    return f"{base}/dish-images/{filename}"


# Registered with and without the trailing slash so proxied requests never hit a
# redirect whose Location points at the internal backend address.
@router.get("", response_model=DishImageResponse, include_in_schema=False)
@router.get("/", response_model=DishImageResponse)
async def get_dish_image(
    request: Request,
    dish_name: str = Query(..., description="Dish name to look up"),
    restaurant_name: str = Query(default="", description="Restaurant name for scoped search (optional)"),
    translated_name: str = Query(default="", max_length=300,
                                 description="The dish's name in the reader's language, if different"),
    description: str = Query(default="", max_length=600,
                             description="The menu's description of the dish; sharpens search and judging"),
) -> DishImageResponse:
    """Return a dish image URL, fetching and caching it on first request.

    Flow:
    1. Check the image_cache table — if hit, return immediately (no network call).
    2. On a miss, search DuckDuckGo, then Wikimedia Commons, each in its own wording
       (see image_sources.py).
    3. Download a shortlist of results and ask DeepSeek which one actually shows the dish
       (see image_judge.py); with no API key the first usable result is used instead.
    4. If nothing fits, ask DeepSeek what an image library would call the dish and search again.
    5. Save the chosen photo under ``.cache/dish_images/`` — never one already shown for another
       dish at the same restaurant.
    6. Return the URL of the locally-served file, plus a credit line when the license needs one.

    Only step 2 onwards counts toward the per-visitor limit. A cached photo, or a dish that just
    failed, costs nothing, and counting those let one page's repeat requests use up a visitor's
    hour of searches before most of its dishes had been looked for.

    A missing photo is normal: when the model says none of the candidates show the dish, this
    returns no image rather than a picture of something else.

    Args:
        dish_name: Name of the dish (e.g. ``"Soon Tofu Jjigae"``).
        restaurant_name: Restaurant name to scope the search (optional).
                        When omitted the search uses the dish name alone.

    Returns:
        ``{ "image_url": "http://…/dish-images/abc123.jpg", "cached": true }``
        or ``{ "image_url": null, "cached": false }`` if nothing was found.
    """
    service = get_dish_image_service()

    # A missing picture must never fail the page: any problem here returns "no image".
    try:
        hit = service.cached_image(restaurant_name, dish_name)
        if hit:
            logger.debug("dish_image: cache hit for '%s'", dish_name)
            return DishImageResponse(
                image_url=_build_image_url(request, hit.filename), cached=True,
                attribution=hit.attribution or "", source=hit.source or "",
            )
        if cache_service.recent_image_failure(restaurant_name, dish_name):
            return DishImageResponse()
    except Exception:
        logger.exception("dish_image: cache lookup failed for '%s'", dish_name)

    # Raises 429 when this visitor has searched too much; outside the try so it reaches the client.
    await enforce_dish_image_limit(request)

    try:
        logger.info("dish_image: cache miss for '%s', searching…", dish_name)
        filename = await service.fetch_and_cache(restaurant_name, dish_name, translated_name, description)
        if not filename:
            return DishImageResponse()

        meta = cache_service.get_image(restaurant_name, dish_name)
        return DishImageResponse(
            image_url=_build_image_url(request, filename), cached=False,
            attribution=(meta.attribution or "") if meta else "",
            source=(meta.source or "") if meta else "",
        )
    except Exception:
        logger.exception("dish_image: unexpected failure for '%s'", dish_name)
        return DishImageResponse()
