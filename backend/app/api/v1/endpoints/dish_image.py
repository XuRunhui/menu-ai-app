"""Dish image API endpoint — search, cache, and serve per-dish images."""

import logging

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel
from typing import Optional

from app.services.dish_image_service import get_dish_image_service

router = APIRouter()
logger = logging.getLogger(__name__)


class DishImageResponse(BaseModel):
    """Response shape for the dish image endpoint."""

    image_url: Optional[str] = None
    cached: bool = False


def _build_image_url(request: Request, filename: str) -> str:
    """Construct the full URL to the locally-served dish image."""
    base = str(request.base_url).rstrip("/")
    return f"{base}/dish-images/{filename}"


@router.get("/", response_model=DishImageResponse)
async def get_dish_image(
    request: Request,
    dish_name: str = Query(..., description="Dish name to look up"),
    restaurant_name: str = Query(default="", description="Restaurant name for scoped search (optional)"),
) -> DishImageResponse:
    """Return a dish image URL, fetching and caching it on first request.

    Flow:
    1. Check local DB cache — if hit, return immediately (no network call).
    2. On cache miss, run a DuckDuckGo image search for
       ``"{restaurant_name} {dish_name} food"`` (restaurant_name omitted if empty).
    3. Download the first usable result, save to ``.cache/dish_images/``,
       record in ``.cache/dish_image_db.json``.
    4. Return the URL pointing to the locally-served static file.

    Args:
        dish_name: Name of the dish (e.g. ``"Soon Tofu Jjigae"``).
        restaurant_name: Restaurant name to scope the search (optional).
                        When omitted the search uses the dish name alone.

    Returns:
        ``{ "image_url": "http://…/dish-images/abc123.jpg", "cached": true }``
        or ``{ "image_url": null, "cached": false }`` if nothing was found.
    """
    service = get_dish_image_service()

    # 1. Cache check
    filename = service.get_cached_filename(restaurant_name, dish_name)
    if filename:
        logger.debug("dish_image: cache hit for '%s'", dish_name)
        return DishImageResponse(
            image_url=_build_image_url(request, filename),
            cached=True,
        )

    # 2. Fetch and cache
    logger.info("dish_image: cache miss for '%s', fetching…", dish_name)
    filename = await service.fetch_and_cache(restaurant_name, dish_name)

    if filename:
        return DishImageResponse(
            image_url=_build_image_url(request, filename),
            cached=False,
        )

    return DishImageResponse(image_url=None, cached=False)
