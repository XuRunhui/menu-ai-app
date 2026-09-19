"""Google Places API endpoints for restaurant data collection."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import logging

from app.services.google_places_service import GooglePlacesService
from app.services.dish_extractor import extract_popular_dishes
from app.models.google_places import (
    PlaceSearchRequest,
    PlaceSearchResponse,
    PlaceData,
)
from app.core.config import settings
from app.core.rate_limit import enforce_demo_limits
from app.api.v1.endpoints.auth import get_optional_user
from app.api.v1.endpoints.library import record_restaurant_view
from app.db.models import User
from app.db.session import get_db
from app.services import cache_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/search", response_model=PlaceSearchResponse, dependencies=[Depends(enforce_demo_limits)])
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

        # REQUEST_DENIED / OVER_QUERY_LIMIT must not look like "no restaurants found".
        if result["status"] not in ("OK", "ZERO_RESULTS"):
            detail = f"Google Places error: {result['status']}"
            if result.get("error_message"):
                detail = f"{detail} - {result['error_message']}"
            logger.error(detail)
            raise HTTPException(status_code=502, detail=detail)

        return {
            "results": result["results"],
            "status": result["status"]
        }

    except HTTPException:
        raise
    except Exception as e:
        msg = f"Place search failed: {str(e)}"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg) from e


@router.get("/{place_id}", response_model=PlaceData, dependencies=[Depends(enforce_demo_limits)])
async def get_place(
    place_id: str,
    label: str | None = Query(None, max_length=255, description="The user's search text, shown in their history"),
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
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

    if not settings.deepseek_api_key:
        msg = "DEEPSEEK_API_KEY environment variable not set"
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
                settings.deepseek_api_key,
                top_n=10
            )
            logger.info(f"Extracted {len(popular_dishes)} popular dishes")
        else:
            logger.info("No reviews available for dish extraction")

        # Only the place ID is stored (Google's terms forbid storing other Places content).
        cache_service.touch_place(place_id)
        if user is not None:
            record_restaurant_view(db, user, place_id, label)

        return {
            "place": place,
            "reviews": reviews,
            "popular_dishes": popular_dishes,
            "cached_at": None
        }

    except Exception as e:
        msg = f"Failed to fetch place data: {str(e)}"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg) from e
