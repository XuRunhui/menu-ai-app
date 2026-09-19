"""Yelp API integration for restaurant data collection.

This collector uses Yelp Fusion API to fetch business details and photos.
Note: Free tier does NOT include review text access.

Example Usage:
    >>> collector = YelpCollector(api_key="your_yelp_api_key")
    >>> data = collector.collect_all("BCD Tofu House", "Koreatown Los Angeles")
    >>> print(f"Found: {data['business']['name']}, Rating: {data['business']['rating']}")
    Found: BCD Tofu House, Rating: 4.5
"""

import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Yelp API endpoints
YELP_API_BASE = "https://api.yelp.com/v3"
YELP_SEARCH_URL = f"{YELP_API_BASE}/businesses/search"
YELP_DETAILS_URL = f"{YELP_API_BASE}/businesses"


class YelpCollector:
    """Collect restaurant data from Yelp Fusion API.

    Capabilities:
    - Business search (name + location)
    - Business details (rating, photos, hours)
    - Categories and price level

    Limitations (Free Tier):
    - No review text access (requires paid plan)
    - 500 API calls per day
    - Rate limited

    Example:
        collector = YelpCollector("your_api_key")

        # Collect all data
        data = collector.collect_all("Tartine Bakery", "San Francisco")

        # Output structure:
        {
            "business": {
                "id": "tartine-bakery-san-francisco",
                "name": "Tartine Bakery",
                "rating": 4.5,
                "review_count": 5234,
                "photos": ["url1", "url2", "url3"],
                "categories": [{"title": "Bakeries"}],
                "price": "$$"
            },
            "photos": ["url1", "url2", "url3"]
        }
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Yelp collector with API key.

        Args:
            api_key: Yelp Fusion API key (optional, will fail gracefully if None)

        Example:
            >>> collector = YelpCollector("abc123")
            >>> collector.api_key is not None
            True
        """
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}" if api_key else ""
        }

        if not api_key:
            logger.warning("YelpCollector initialized without API key - will fail gracefully")

    def search_business(
        self,
        name: str,
        location: str,
        limit: int = 5
    ) -> Optional[dict]:
        """Search for a business on Yelp.

        Args:
            name: Business name (e.g., "BCD Tofu House")
            location: Location string (e.g., "Koreatown Los Angeles")
            limit: Max results (default 5)

        Returns:
            First matching business dict or None if not found

        Example:
            >>> collector = YelpCollector("key")
            >>> business = collector.search_business("Tartine", "SF")
            >>> business["name"]
            'Tartine Bakery'

        Return Structure:
            {
                "id": "business-id",
                "name": "Business Name",
                "rating": 4.5,
                "review_count": 1234,
                "location": {"address1": "123 Main St", ...},
                "coordinates": {"latitude": 37.7749, "longitude": -122.4194},
                "categories": [{"alias": "bakeries", "title": "Bakeries"}],
                "price": "$$"
            }
        """
        if not self.api_key:
            logger.warning("Yelp: No API key, skipping search")
            return None

        try:
            logger.info(f"Yelp: Searching for '{name}' in '{location}'")

            params = {
                "term": name,
                "location": location,
                "limit": limit
            }

            response = requests.get(
                YELP_SEARCH_URL,
                headers=self.headers,
                params=params,
                timeout=10
            )
            response.raise_for_status()

            data = response.json()
            businesses = data.get("businesses", [])

            if businesses:
                business = businesses[0]  # Get first match
                logger.info(f"Yelp: Found '{business['name']}' (rating: {business.get('rating')})")
                return business
            else:
                logger.info(f"Yelp: No results for '{name}'")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Yelp search failed: {e}")
            return None

    def get_business_details(self, business_id: str) -> Optional[dict]:
        """Get detailed business information.

        Args:
            business_id: Yelp business ID

        Returns:
            Business details dict or None if failed

        Example:
            >>> collector = YelpCollector("key")
            >>> details = collector.get_business_details("tartine-bakery-sf")
            >>> len(details["photos"])
            3

        Return Structure:
            {
                "id": "business-id",
                "name": "Business Name",
                "rating": 4.5,
                "review_count": 1234,
                "photos": ["url1", "url2", "url3"],  # Up to 3 photos
                "hours": [{"open": [{"start": "0800", "end": "2000"}]}],
                "categories": [...],
                "price": "$$"
            }
        """
        if not self.api_key:
            logger.warning("Yelp: No API key, skipping details")
            return None

        try:
            logger.info(f"Yelp: Fetching details for business ID: {business_id}")

            url = f"{YELP_DETAILS_URL}/{business_id}"
            response = requests.get(
                url,
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()

            data = response.json()
            logger.info(f"Yelp: Retrieved details for '{data['name']}'")
            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Yelp details failed: {e}")
            return None

    def collect_all(
        self,
        restaurant_name: str,
        location: str
    ) -> dict:
        """Collect all available data from Yelp.

        This is the main entry point - searches for business and fetches details.

        Args:
            restaurant_name: Name of restaurant
            location: Location string

        Returns:
            Dictionary with business info and photos

        Example:
            >>> collector = YelpCollector("key")
            >>> data = collector.collect_all("BCD Tofu House", "Koreatown LA")
            >>> print(data["business"]["rating"])
            4.5
            >>> print(len(data["photos"]))
            3

        Return Structure:
            {
                "business": {
                    "id": "bcd-tofu-house-koreatown",
                    "name": "BCD Tofu House",
                    "rating": 4.5,
                    "review_count": 3456,
                    "categories": [{"title": "Korean"}],
                    "price": "$$",
                    "location": {...},
                    "coordinates": {...}
                },
                "photos": ["url1", "url2", "url3"],
                "success": true
            }

        Debug Example:
            # Uncomment to test with a real restaurant
            # collector = YelpCollector(os.getenv("YELP_API_KEY"))
            # result = collector.collect_all("Tartine Bakery", "San Francisco")
            # print(json.dumps(result, indent=2))
        """
        logger.info(f"Yelp: Collecting all data for '{restaurant_name}', '{location}'")

        # Search for business
        business = self.search_business(restaurant_name, location)

        if not business:
            logger.info("Yelp: Business not found, returning empty result")
            return {
                "business": None,
                "photos": [],
                "success": False,
                "error": "Business not found"
            }

        # Get detailed info
        business_id = business["id"]
        details = self.get_business_details(business_id)

        if not details:
            logger.warning("Yelp: Failed to fetch details, using search result only")
            details = business

        # Extract photos
        photos = details.get("photos", [])

        result = {
            "business": details,
            "photos": photos,
            "success": True
        }

        logger.info(
            f"Yelp: Collection complete - "
            f"Rating: {details.get('rating')}, "
            f"Photos: {len(photos)}, "
            f"Reviews: {details.get('review_count')}"
        )

        return result


# Debug/Testing Examples (commented out)
"""
# Example 1: Basic usage
if __name__ == "__main__":
    import os
    import json

    collector = YelpCollector(os.getenv("YELP_API_KEY"))

    # Test with a well-known restaurant
    result = collector.collect_all("Tartine Bakery", "San Francisco")
    print(json.dumps(result, indent=2))

    # Expected output:
    # {
    #   "business": {
    #     "name": "Tartine Bakery",
    #     "rating": 4.5,
    #     "photos": ["url1", "url2", "url3"]
    #   },
    #   "success": true
    # }

# Example 2: Error handling test
if __name__ == "__main__":
    # Test without API key (should fail gracefully)
    collector = YelpCollector(None)
    result = collector.collect_all("Any Restaurant", "Anywhere")
    assert result["success"] == False
    print("✓ Graceful failure test passed")

# Example 3: Multiple restaurants
if __name__ == "__main__":
    import os

    collector = YelpCollector(os.getenv("YELP_API_KEY"))

    restaurants = [
        ("BCD Tofu House", "Koreatown Los Angeles"),
        ("Tartine Bakery", "San Francisco"),
        ("Joe's Pizza", "New York")
    ]

    for name, loc in restaurants:
        result = collector.collect_all(name, loc)
        if result["success"]:
            print(f"✓ {name}: {result['business']['rating']} stars")
        else:
            print(f"✗ {name}: Not found")
"""
