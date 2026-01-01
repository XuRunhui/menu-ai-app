"""Yelp Fusion API integration for restaurant data collection."""

import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

YELP_API_BASE = "https://api.yelp.com/v3"


class YelpService:
    """Service for interacting with Yelp Fusion API."""

    def __init__(self, api_key: str):
        """Initialize Yelp service with API key.

        Args:
            api_key: Yelp Fusion API key.
        """
        self.api_key = api_key
        self.headers = {"Authorization": f"Bearer {api_key}"}

    def search_businesses(
        self,
        name: str,
        location: str,
        limit: int = 5
    ) -> dict:
        """Search for businesses by name and location.

        Args:
            name: Restaurant name to search for.
            location: Location (city, state, or zip code).
            limit: Maximum number of results to return.

        Returns:
            Dictionary with 'businesses' and 'total' keys.

        Raises:
            requests.HTTPError: If API request fails.
        """
        url = f"{YELP_API_BASE}/businesses/search"
        params = {
            "term": name,
            "location": location,
            "limit": limit,
        }

        logger.info(f"Searching Yelp for: {name} in {location}")

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            businesses = data.get("businesses", [])
            total = data.get("total", 0)

            logger.info(f"Found {len(businesses)} businesses (total: {total})")
            return {"businesses": businesses, "total": total}

        except requests.exceptions.RequestException as e:
            logger.error(f"Yelp search failed: {e}")
            raise

    def get_business_details(self, business_id: str) -> dict:
        """Get detailed business information.

        Args:
            business_id: Yelp business ID.

        Returns:
            Business details dictionary.

        Raises:
            requests.HTTPError: If API request fails.
        """
        url = f"{YELP_API_BASE}/businesses/{business_id}"

        logger.info(f"Fetching details for business: {business_id}")

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()

            business = response.json()
            logger.info(f"Retrieved details for: {business.get('name')}")
            return business

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch business details: {e}")
            raise

    def get_reviews(self, business_id: str, limit: int = 10) -> list[dict]:
        """Get reviews for a business.

        Args:
            business_id: Yelp business ID.
            limit: Maximum number of reviews (max 3 per Yelp API).

        Returns:
            List of review dictionaries. Returns empty list if reviews unavailable.
        """
        url = f"{YELP_API_BASE}/businesses/{business_id}/reviews"
        # Note: Yelp API only returns max 3 reviews
        params = {"limit": min(limit, 3)}

        logger.info(f"Fetching reviews for business: {business_id}")

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            reviews = data.get("reviews", [])

            logger.info(f"Retrieved {len(reviews)} reviews")
            return reviews

        except requests.exceptions.HTTPError as e:
            # Reviews endpoint might not be available for all businesses
            # or might require additional API permissions
            if e.response.status_code == 404:
                logger.warning(f"Reviews not available for business {business_id} (404)")
                return []
            else:
                logger.error(f"Failed to fetch reviews: {e}")
                raise
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to fetch reviews (non-critical): {e}")
            return []

    def get_full_restaurant_data(self, business_id: str) -> dict:
        """Get complete restaurant data (details + reviews).

        Args:
            business_id: Yelp business ID.

        Returns:
            Dictionary with 'business' and 'reviews' keys.

        Raises:
            requests.HTTPError: If API request fails.
        """
        business = self.get_business_details(business_id)
        reviews = self.get_reviews(business_id)

        return {
            "business": business,
            "reviews": reviews
        }
