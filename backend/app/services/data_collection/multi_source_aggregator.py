"""Aggregate data from multiple sources with fault tolerance."""

import asyncio
import logging
import re
from typing import Optional

from app.services import cache_service
from app.services.google_places_service import GooglePlacesService
from .ddgs_collector import DDGSCollector
from .yelp_collector import YelpCollector

logger = logging.getLogger(__name__)


class MultiSourceAggregator:
    """Collect data from all available sources, handle failures gracefully.

    This aggregator combines data from multiple sources:
    1. Google Places API - Reviews (5) + Photos (10) + Ratings
    2. DuckDuckGo Search - Web reviews (20) + Images (10)
    3. Yelp API - Business info + Photos (3)

    All sources are fault-tolerant: if one fails, others continue.

    Example:
        >>> aggregator = MultiSourceAggregator(
        ...     google_api_key="key1",
        ...     yelp_api_key="key2"
        ... )
        >>> data = await aggregator.collect_all_data(
        ...     "BCD Tofu House",
        ...     "Koreatown Los Angeles",
        ...     place_id="ChIJ..."
        ... )
        >>> print(f"Sources: {data['sources']}")
        Sources: ['Google Places', 'DuckDuckGo', 'Yelp']
        >>> print(f"Total reviews: {len(data['reviews'])}")
        Total reviews: 25
    """

    def __init__(
        self,
        google_api_key: Optional[str] = None,
        yelp_api_key: Optional[str] = None,
        cache_enabled: bool = True,
        cache_ttl_seconds: int = 604800
    ):
        """Initialize aggregator with API keys.

        Args:
            google_api_key: Google Places API key (optional)
            yelp_api_key: Yelp Fusion API key (optional)
            cache_enabled: Reuse DuckDuckGo results from the web_search_cache table
                (Google and Yelp are always fetched live; their terms don't allow storing content)
            cache_ttl_seconds: Kept for compatibility; the cache TTL lives in cache_service

        Example:
            >>> # With all keys
            >>> aggregator = MultiSourceAggregator(
            ...     google_api_key="AIza...",
            ...     yelp_api_key="abc123..."
            ... )
            >>> # Will use all 3 sources

            >>> # Without Yelp (still works!)
            >>> aggregator = MultiSourceAggregator(google_api_key="AIza...")
            >>> # Will use Google + DuckDuckGo only
        """
        self.google = GooglePlacesService(google_api_key) if google_api_key else None
        self.ddgs = DDGSCollector()
        self.yelp = YelpCollector(yelp_api_key) if yelp_api_key else None
        self.cache_enabled = cache_enabled

        # Log which sources are available
        available = []
        if self.google:
            available.append("Google Places")
        available.append("DuckDuckGo")  # Always available (free)
        if self.yelp:
            available.append("Yelp")

        logger.info(f"MultiSourceAggregator initialized with sources: {', '.join(available)}")

    async def collect_all_data(
        self,
        restaurant_name: str,
        location: str,
        place_id: Optional[str] = None
    ) -> dict:
        """Collect data from all sources in parallel.

        Strategy:
        - Run all collectors concurrently
        - Continue even if some fail
        - Return aggregated results from successful sources

        Args:
            restaurant_name: Restaurant name
            location: Location string
            place_id: Google Place ID (if known)

        Returns:
            Aggregated data dictionary
        """
        logger.info(f"Starting multi-source collection for {restaurant_name}, {location}")

        # Run all collectors in parallel; DuckDuckGo results may come from the cache.
        cached_ddgs = (
            cache_service.get_web_search(restaurant_name, location) if self.cache_enabled else None
        )

        tasks = []
        if self.google and place_id:
            tasks.append(self._safe_collect_google(place_id))
        if self.ddgs and cached_ddgs is None:
            tasks.append(self._safe_collect_ddgs(restaurant_name, location))
        if self.yelp:
            tasks.append(self._safe_collect_yelp(restaurant_name, location))

        results = list(await asyncio.gather(*tasks, return_exceptions=True))

        if cached_ddgs is not None:
            logger.info(f"DuckDuckGo cache hit for {restaurant_name}, {location}")
            results.append({"source": "DuckDuckGo", "data": cached_ddgs[0], "success": True})
        elif self.cache_enabled:
            for result in results:
                if (
                    isinstance(result, dict)
                    and result.get("source") == "DuckDuckGo"
                    and result.get("success")
                    and (result["data"].get("reviews") or result["data"].get("images"))
                ):
                    cache_service.set_web_search(restaurant_name, location, result["data"])

        aggregated = self._aggregate_results(results)
        aggregated["metadata"]["cache_hit"] = cached_ddgs is not None
        if cached_ddgs is not None:
            aggregated["metadata"]["cached_at"] = cached_ddgs[1].isoformat()
        return aggregated

    async def _safe_collect_google(self, place_id: str) -> dict:
        """Safely collect from Google Places."""
        try:
            logger.info("Collecting from Google Places...")
            data = self.google.get_full_place_data(place_id)

            logger.info("✓ Google Places: Success")
            return {
                "source": "Google Places",
                "data": data,
                "success": True
            }
        except Exception as e:
            logger.warning(f"✗ Google Places: Failed - {e}")
            return {
                "source": "Google Places",
                "data": None,
                "success": False,
                "error": str(e)
            }

    async def _safe_collect_ddgs(self, restaurant_name: str, location: str) -> dict:
        """Safely collect from DuckDuckGo."""
        try:
            logger.info("Collecting from DuckDuckGo...")
            data = self.ddgs.collect_all(restaurant_name, location)

            logger.info("✓ DuckDuckGo: Success")
            return {
                "source": "DuckDuckGo",
                "data": data,
                "success": True
            }
        except Exception as e:
            logger.warning(f"✗ DuckDuckGo: Failed - {e}")
            return {
                "source": "DuckDuckGo",
                "data": None,
                "success": False,
                "error": str(e)
            }

    async def _safe_collect_yelp(self, restaurant_name: str, location: str) -> dict:
        """Safely collect from Yelp.

        Note: Yelp often fails for some restaurants but works for others.
        This is expected behavior - we continue with other sources.

        Args:
            restaurant_name: Restaurant name
            location: Location string

        Returns:
            Result dictionary with success flag

        Example Success:
            {
                "source": "Yelp",
                "data": {
                    "business": {"name": "...", "rating": 4.5, ...},
                    "photos": ["url1", "url2", "url3"]
                },
                "success": True
            }

        Example Failure (restaurant not found):
            {
                "source": "Yelp",
                "data": None,
                "success": False,
                "error": "Business not found"
            }
        """
        try:
            logger.info("Collecting from Yelp...")
            data = self.yelp.collect_all(restaurant_name, location)

            if data.get("success"):
                logger.info("✓ Yelp: Success")
                return {
                    "source": "Yelp",
                    "data": data,
                    "success": True
                }
            else:
                # Yelp returned but didn't find business
                logger.info(f"✗ Yelp: {data.get('error', 'Not found')}")
                return {
                    "source": "Yelp",
                    "data": None,
                    "success": False,
                    "error": data.get("error", "Not found")
                }
        except Exception as e:
            logger.warning(f"✗ Yelp: Failed - {e}")
            return {
                "source": "Yelp",
                "data": None,
                "success": False,
                "error": str(e)
            }

    def _aggregate_results(self, results: list) -> dict:
        """Aggregate data from all sources.

        Args:
            results: List of collection results

        Returns:
            Aggregated data dictionary
        """
        aggregated = {
            "reviews": [],
            "images": [],
            "popular_dishes": [],
            "place_info": None,
            "sources": [],
            "metadata": {
                "total_sources": len(results),
                "successful_sources": 0,
                "failed_sources": []
            }
        }

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Collection task failed with exception: {result}")
                continue

            if not result.get("success"):
                aggregated["metadata"]["failed_sources"].append({
                    "source": result["source"],
                    "error": result.get("error")
                })
                continue

            aggregated["metadata"]["successful_sources"] += 1
            source = result["source"]
            data = result["data"]
            aggregated["sources"].append(source)

            # Handle Google Places data
            if source == "Google Places":
                place = data.get("place", {})
                reviews = data.get("reviews", [])
                popular_dishes = data.get("popular_dishes", [])

                # Store place info
                aggregated["place_info"] = place

                # Add reviews with source tag
                for review in reviews:
                    aggregated["reviews"].append({
                        **review,
                        "_source": "google_places"
                    })

                # Add popular dishes
                aggregated["popular_dishes"].extend(popular_dishes)

            # Handle DuckDuckGo data
            elif source == "DuckDuckGo":
                reviews = data.get("reviews", [])
                images = data.get("images", [])

                # Add reviews with source tag
                for review in reviews:
                    aggregated["reviews"].append({
                        **review,
                        "_source": "ddgs"
                    })

                # Add images
                for image in images:
                    aggregated["images"].append({
                        **image,
                        "_source": "ddgs"
                    })
            # Handle Yelp data
            elif source == "Yelp":
                photos = data.get("photos", [])
                for photo_url in photos:
                    aggregated["images"].append({
                        "url": photo_url,
                        "source": "yelp",
                        "type": "restaurant_photo"
                    })

        # Deduplicate
        aggregated["reviews"] = self._deduplicate_reviews(aggregated["reviews"])
        aggregated["images"] = self._deduplicate_images(aggregated["images"])

        logger.info(
            f"Aggregation complete: "
            f"{len(aggregated['reviews'])} reviews, "
            f"{len(aggregated['images'])} images from "
            f"{aggregated['metadata']['successful_sources']} sources"
        )

        return aggregated

    def _deduplicate_reviews(self, reviews: list) -> list:
        """Remove duplicate reviews based on text similarity.

        Args:
            reviews: List of review dictionaries

        Returns:
            Deduplicated list
        """
        # Quick deduplication by normalized first 120 characters.
        seen = set()
        unique = []

        for review in reviews:
            text = review.get("text", "")
            normalized = self._normalize_review_text(text)
            key = normalized[:120]
            if key and key not in seen:
                seen.add(key)
                unique.append(review)

        removed = len(reviews) - len(unique)
        if removed > 0:
            logger.info(f"Removed {removed} duplicate reviews")

        return unique

    def _normalize_review_text(self, text: str) -> str:
        """Normalize text for basic deduplication."""
        normalized = re.sub(r"[^a-z0-9\s]", "", text.lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def _deduplicate_images(self, images: list) -> list:
        """Remove duplicate images by URL.

        Args:
            images: List of image dictionaries

        Returns:
            Deduplicated list
        """
        seen = set()
        unique = []

        for img in images:
            url = img.get("url")
            if url and url not in seen:
                seen.add(url)
                unique.append(img)

        removed = len(images) - len(unique)
        if removed > 0:
            logger.info(f"Removed {removed} duplicate images")

        return unique
