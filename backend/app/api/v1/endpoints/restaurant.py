"""Restaurant API endpoints for Yelp data collection."""

from fastapi import APIRouter, HTTPException
import logging

from app.services.yelp_service import YelpService
from app.services.dish_extractor import extract_popular_dishes
from app.models.restaurant import (
    RestaurantSearchRequest,
    RestaurantSearchResponse,
    RestaurantData,
    YelpBusiness,
    YelpReview,
    PopularDish,
)
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/search", response_model=RestaurantSearchResponse)
async def search_restaurant(request: RestaurantSearchRequest):
    """Search for restaurants by name and location.

    Args:
        request: Restaurant search request with name and location.

    Returns:
        List of matching businesses from Yelp.

    Raises:
        HTTPException: If Yelp API key is not configured or search fails.
    """
    if not settings.yelp_api_key:
        msg = "YELP_API_KEY environment variable not set"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)

    logger.info(f"Searching for restaurant: {request.name} in {request.location}")

    try:
        yelp = YelpService(settings.yelp_api_key)
        result = yelp.search_businesses(request.name, request.location)

        return {
            "businesses": result["businesses"],
            "total": result["total"]
        }

    except Exception as e:
        msg = f"Restaurant search failed: {str(e)}"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg) from e


@router.get("/{business_id}", response_model=RestaurantData)
async def get_restaurant(business_id: str):
    """Get detailed restaurant data including reviews and popular dishes.

    Args:
        business_id: Yelp business ID.

    Returns:
        Complete restaurant data with reviews and extracted popular dishes.

    Raises:
        HTTPException: If API keys are not configured or request fails.
    """
    if not settings.yelp_api_key:
        msg = "YELP_API_KEY environment variable not set"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)

    if not settings.gemini_api_key:
        msg = "GEMINI_API_KEY environment variable not set"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)

    logger.info(f"Fetching restaurant data for: {business_id}")

    try:
        yelp = YelpService(settings.yelp_api_key)

        # Get business details and reviews
        data = yelp.get_full_restaurant_data(business_id)
        business = data["business"]
        reviews = data["reviews"]

        # Extract popular dishes from reviews
        review_texts = [r["text"] for r in reviews]
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
            "business": business,
            "reviews": reviews,
            "popular_dishes": popular_dishes,
            "cached_at": None  # Will add caching in future
        }

    except Exception as e:
        msg = f"Failed to fetch restaurant data: {str(e)}"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg) from e
