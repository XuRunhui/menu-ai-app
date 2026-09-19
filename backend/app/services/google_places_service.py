"""Google Places API integration for restaurant data collection.

Note: This uses the legacy Places API endpoints which work with simple API keys.
The new Places API (v1) requires different authentication and endpoints.
For this implementation, we use the legacy API which is still fully supported.

Place photos are deliberately not used. They added about 2% of menu dishes, cost a billed
request per photo, came without the dish they were shown for, and Google's terms require crediting
the photographer wherever one is displayed. Dish photos come from DuckDuckGo and Wikimedia
Commons instead (see image_sources.py).
"""

import requests

from app.core.rate_limit import claim_places_call
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Using legacy Places API endpoints (still supported and works with API keys)
GOOGLE_PLACES_API_BASE = "https://maps.googleapis.com/maps/api"


class GooglePlacesService:
    """Service for interacting with Google Places API."""

    def __init__(self, api_key: str):
        """Initialize Google Places service with API key.

        Args:
            api_key: Google Places API key.
        """
        self.api_key = api_key

    def search_places(
        self,
        query: str,
        location: Optional[str] = None,
        radius: int = 50000,
        use_exact_match: bool = True
    ) -> dict:
        """Search for places using Find Place or Text Search API.

        Args:
            query: Search query (e.g., "Tartine Bakery San Francisco" or
                   "Sun Nong Dan 3463 W 6th St Los Angeles CA").
            location: Optional lat,lng for biasing results.
            radius: Search radius in meters (default 50km).
            use_exact_match: Use Find Place API for exact matching (default True).

        Returns:
            Dictionary with 'results' and 'status' keys.

        Raises:
            requests.HTTPError: If API request fails.
        """
        # Try exact match first (Find Place from Text API)
        if use_exact_match:
            logger.info(f"Trying exact match search for: {query}")
            exact_result = self._find_place_from_text(query)

            if exact_result["status"] == "OK" and exact_result["results"]:
                logger.info(f"Exact match found: {len(exact_result['results'])} place(s)")
                return exact_result
            else:
                logger.info(f"Exact match not found (status: {exact_result['status']}), falling back to text search")

        # Fallback to broader text search
        return self._text_search(query, location, radius)

    def _find_place_from_text(self, query: str) -> dict:
        """Find exact place using Find Place from Text API.

        This is more precise for name + address combinations.

        Args:
            query: Combined name and address string.

        Returns:
            Dictionary with 'results' and 'status' keys.
        """
        url = f"{GOOGLE_PLACES_API_BASE}/place/findplacefromtext/json"
        params = {
            "input": query,
            "inputtype": "textquery",
            "fields": "place_id,name,formatted_address,rating,user_ratings_total,"
                     "price_level,types,geometry,business_status",
            "key": self.api_key,
        }

        try:
            claim_places_call()  # the site-wide daily budget
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            status = data.get("status")
            candidates = data.get("candidates", [])

            # Convert candidates to results format for consistency
            return {"results": candidates, "status": status}

        except requests.exceptions.RequestException as e:
            logger.error(f"Find place from text failed: {e}")
            return {"results": [], "status": "ERROR"}

    def _text_search(self, query: str, location: Optional[str] = None, radius: int = 50000) -> dict:
        """Broader text search (original implementation).

        Args:
            query: Search query.
            location: Optional lat,lng for biasing results.
            radius: Search radius in meters.

        Returns:
            Dictionary with 'results' and 'status' keys.
        """
        url = f"{GOOGLE_PLACES_API_BASE}/place/textsearch/json"
        params = {
            "query": query,
            "key": self.api_key,
        }

        if location:
            params["location"] = location
            params["radius"] = radius

        logger.info(f"Text search for: {query}")

        try:
            claim_places_call()  # the site-wide daily budget
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            status = data.get("status")
            results = data.get("results", [])

            if status not in ("OK", "ZERO_RESULTS"):
                # e.g. REQUEST_DENIED (key restriction or API not enabled), OVER_QUERY_LIMIT
                logger.warning(f"Google Places API status: {status} - {data.get('error_message', '')}")
                return {"results": [], "status": status, "error_message": data.get("error_message", "")}

            for result in results:
                result.pop("photos", None)   # this app doesn't use Google place photos
            logger.info(f"Found {len(results)} places")
            return {"results": results, "status": status}

        except requests.exceptions.RequestException as e:
            logger.error(f"Google Places search failed: {e}")
            raise

    def get_place_details(self, place_id: str) -> dict:
        """Get detailed place information.

        Args:
            place_id: Google Place ID.

        Returns:
            Place details dictionary.

        Raises:
            requests.HTTPError: If API request fails.
        """
        url = f"{GOOGLE_PLACES_API_BASE}/place/details/json"
        params = {
            "place_id": place_id,
            "fields": "place_id,name,rating,user_ratings_total,price_level,formatted_address,"
                     "formatted_phone_number,opening_hours,website,geometry,types,reviews",
            "key": self.api_key,
        }

        logger.info(f"Fetching details for place: {place_id}")

        try:
            claim_places_call()  # the site-wide daily budget
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            status = data.get("status")

            if status != "OK":
                logger.warning(f"Google Places API status: {status}")
                raise ValueError(f"Failed to get place details: {status}")

            result = data.get("result", {})
            logger.info(f"Retrieved details for: {result.get('name')}")
            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch place details: {e}")
            raise

    def get_menu_fields(self, place_id: str) -> dict:
        """Just what finding a menu needs: the name and the website.

        Narrower than get_place_details on purpose — no reviews or opening hours, so it bills at
        the cheaper Place Details SKUs.
        """
        claim_places_call()  # the site-wide daily budget
        response = requests.get(
            f"{GOOGLE_PLACES_API_BASE}/place/details/json",
            params={"place_id": place_id, "fields": "place_id,name,website", "key": self.api_key},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "OK":
            raise ValueError(f"Failed to get place details: {data.get('status')}")
        return data.get("result", {})

    def get_full_place_data(self, place_id: str) -> dict:
        """Get complete place data (details + reviews).

        Args:
            place_id: Google Place ID.

        Returns:
            Dictionary with 'place' and 'reviews' keys.
        """
        place = self.get_place_details(place_id)
        reviews = place.get("reviews", [])

        return {
            "place": place,
            "reviews": reviews
        }
