"""Google Places API integration for restaurant data collection.

Note: This uses the legacy Places API endpoints which work with simple API keys.
The new Places API (v1) requires different authentication and endpoints.
For this implementation, we use the legacy API which is still fully supported.
"""

import requests
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
                     "price_level,types,geometry,photos,business_status",
            "key": self.api_key,
        }

        try:
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
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            status = data.get("status")
            results = data.get("results", [])

            if status != "OK" and status != "ZERO_RESULTS":
                logger.warning(f"Google Places API status: {status}")

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
                     "formatted_phone_number,opening_hours,website,photos,geometry,types,reviews",
            "key": self.api_key,
        }

        logger.info(f"Fetching details for place: {place_id}")

        try:
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

    def get_photo_url(self, photo_reference: str, max_width: int = 400) -> str:
        """Get URL for a place photo.

        Args:
            photo_reference: Photo reference from place details.
            max_width: Maximum width of the photo.

        Returns:
            Photo URL.
        """
        return (
            f"{GOOGLE_PLACES_API_BASE}/place/photo"
            f"?maxwidth={max_width}"
            f"&photoreference={photo_reference}"
            f"&key={self.api_key}"
        )

    def get_full_place_data(self, place_id: str) -> dict:
        """Get complete place data (details + reviews).

        Args:
            place_id: Google Place ID.

        Returns:
            Dictionary with 'place' and 'reviews' keys.
        """
        place = self.get_place_details(place_id)
        reviews = place.get("reviews", [])

        # Process photo URLs
        photos = place.get("photos", [])
        photo_urls = []
        for photo in photos[:5]:  # Get up to 5 photos
            photo_ref = photo.get("photo_reference")
            if photo_ref:
                photo_urls.append(self.get_photo_url(photo_ref, max_width=800))

        place["photo_urls"] = photo_urls

        return {
            "place": place,
            "reviews": reviews
        }
