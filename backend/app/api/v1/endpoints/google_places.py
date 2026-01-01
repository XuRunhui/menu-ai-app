"""Google Places API endpoints for restaurant data collection."""

from fastapi import APIRouter, HTTPException
import logging

from app.services.google_places_service import GooglePlacesService
from app.services.dish_extractor import extract_popular_dishes
from app.models.google_places import (
    PlaceSearchRequest,
    PlaceSearchResponse,
    PlaceData,
)
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/search", response_model=PlaceSearchResponse)
async def search_places(request: PlaceSearchRequest):
    """Search for places by query.

    Args:
        request: Place search request with query and optional location.

    Returns:
        List of matching places from Google Places.

    Raises:
        HTTPException: If Google Places API key is not configured or search fails.
    """
    if not settings.google_places_api_key:
        msg = "GOOGLE_PLACES_API_KEY environment variable not set"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)

    logger.info(f"Searching for place: {request.query}")

    try:
        google_places = GooglePlacesService(settings.google_places_api_key)

        # Combine query with location if provided
        query = request.query
        if request.location:
            query = f"{request.query} {request.location}"

        # Use text search (not exact match) to get multiple results
        # This is better for vague queries like "best sushi downtown"
        result = google_places.search_places(query, use_exact_match=False)

        return {
            "results": result["results"],
            "status": result["status"]
        }

    except Exception as e:
        msg = f"Place search failed: {str(e)}"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg) from e


@router.get("/{place_id}", response_model=PlaceData)
async def get_place(place_id: str):
    """Get detailed place data including reviews and popular dishes.

    Args:
        place_id: Google Place ID.

    Returns:
        Complete place data with reviews and extracted popular dishes.

    Raises:
        HTTPException: If API keys are not configured or request fails.
    """
    if not settings.google_places_api_key:
        msg = "GOOGLE_PLACES_API_KEY environment variable not set"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)

    if not settings.gemini_api_key:
        msg = "GEMINI_API_KEY environment variable not set"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)

    logger.info(f"Fetching place data for: {place_id}")

    try:
        google_places = GooglePlacesService(settings.google_places_api_key)

        # Get place details and reviews
        data = google_places.get_full_place_data(place_id)
        place = data["place"]
        reviews = data["reviews"]

        # Extract popular dishes from reviews
        review_texts = [r.get("text", "") for r in reviews if r.get("text")]
        popular_dishes = []

        if review_texts:
            logger.info(f"Extracting popular dishes from {len(review_texts)} reviews")
            popular_dishes = extract_popular_dishes(
                review_texts,
                settings.gemini_api_key,
                top_n=10
            )
            logger.info(f"Extracted {len(popular_dishes)} popular dishes")
        else:
            logger.info("No reviews available for dish extraction")

        return {
            "place": place,
            "reviews": reviews,
            "popular_dishes": popular_dishes,
            "cached_at": None  # Will add caching in future
        }

    except Exception as e:
        msg = f"Failed to fetch place data: {str(e)}"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg) from e
