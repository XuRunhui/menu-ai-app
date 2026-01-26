"""DuckDuckGo search integration for reviews and images."""

from duckduckgo_search import DDGS
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DDGSCollector:
    """Collect restaurant data from web via DuckDuckGo."""

    def __init__(self):
        """Initialize DDGS collector."""
        self.ddgs = DDGS()

    def collect_reviews(
        self,
        restaurant_name: str,
        location: str,
        max_results: int = 20
    ) -> list[dict]:
        """Collect reviews from Yelp and TripAdvisor via DuckDuckGo.

        Args:
            restaurant_name: Name of the restaurant
            location: Location (e.g., "Koreatown Los Angeles")
            max_results: Maximum number of results

        Returns:
            List of review snippets with metadata
        """
        query = f"{restaurant_name} {location} reviews site:yelp.com OR site:tripadvisor.com"

        try:
            logger.info(f"DDGS: Searching for reviews: {query}")
            results = self.ddgs.text(query, max_results=max_results)

            reviews = []
            for r in results:
                reviews.append({
                    "source": "ddgs_web",
                    "title": r["title"],
                    "text": r["body"],
                    "url": r["href"],
                    "snippet": True  # Flag as snippet, not full review
                })

            logger.info(f"DDGS: Collected {len(reviews)} review snippets")
            return reviews

        except Exception as e:
            logger.error(f"DDGS review collection failed: {e}")
            return []  # Graceful failure

    def collect_dish_images(
        self,
        restaurant_name: str,
        dish_name: Optional[str] = None,
        max_results: int = 10
    ) -> list[dict]:
        """Collect dish images via DuckDuckGo image search.

        Args:
            restaurant_name: Name of restaurant
            dish_name: Specific dish name (optional)
            max_results: Maximum images to fetch

        Returns:
            List of image URLs with metadata
        """
        if dish_name:
            query = f"{restaurant_name} {dish_name} food"
        else:
            query = f"{restaurant_name} food menu dishes"

        try:
            logger.info(f"DDGS: Searching for images: {query}")
            results = self.ddgs.images(query, max_results=max_results)

            images = []
            for img in results:
                images.append({
                    "source": "ddgs_images",
                    "title": img["title"],
                    "url": img["image"],
                    "thumbnail": img.get("thumbnail"),
                    "source_url": img["source"],
                    "dish_hint": dish_name  # For matching later
                })

            logger.info(f"DDGS: Collected {len(images)} images")
            return images

        except Exception as e:
            logger.error(f"DDGS image collection failed: {e}")
            return []

    def collect_all(
        self,
        restaurant_name: str,
        location: str,
        include_images: bool = True
    ) -> dict:
        """Collect all available data from DDGS.

        Args:
            restaurant_name: Restaurant name
            location: Location string
            include_images: Whether to collect images

        Returns:
            Dictionary with reviews and images
        """
        logger.info(f"DDGS: Collecting all data for {restaurant_name}, {location}")

        data = {
            "reviews": self.collect_reviews(restaurant_name, location),
            "images": []
        }

        if include_images:
            data["images"] = self.collect_dish_images(restaurant_name)

        logger.info(
            f"DDGS: Collection complete - "
            f"{len(data['reviews'])} reviews, {len(data['images'])} images"
        )

        return data
