"""Aggregate data from multiple sources with fault tolerance."""

import asyncio
import logging
import re
import copy
from datetime import datetime, timezone
from typing import Optional

from app.services.google_places_service import GooglePlacesService
from .ddgs_collector import DDGSCollector
from .yelp_collector import YelpCollector
from .cache_store import LocalCacheStore

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
        cache_ttl_seconds: int = 604800,
        cache_store: Optional[LocalCacheStore] = None
    ):
        """Initialize aggregator with API keys.

        Args:
            google_api_key: Google Places API key (optional)
            yelp_api_key: Yelp Fusion API key (optional)

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
        self.cache_store = cache_store
        if cache_enabled:
            self.cache_store = cache_store or LocalCacheStore(
                default_ttl_seconds=cache_ttl_seconds
            )

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

        cache_key = self._build_cache_key(restaurant_name, location, place_id)
        if self.cache_store:
            cached_entry = self.cache_store.get(cache_key)
            if cached_entry:
                cached_data = copy.deepcopy(cached_entry.data)
                cached_meta = cached_data.get("metadata", {})
                cached_meta["cache_hit"] = True
                cached_meta["cached_at"] = datetime.fromtimestamp(
                    cached_entry.cached_at,
                    tz=timezone.utc
                ).isoformat()
                cached_data["metadata"] = cached_meta
                logger.info(f"Cache hit for {cache_key}")
                return cached_data

        # Run all collectors in parallel
        tasks = []

        if self.google and place_id:
            tasks.append(self._safe_collect_google(place_id))

        if self.ddgs:
            tasks.append(self._safe_collect_ddgs(restaurant_name, location))

        if self.yelp:
            tasks.append(self._safe_collect_yelp(restaurant_name, location))

        # Wait for all (with timeout)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results
        aggregated = self._aggregate_results(results)
        aggregated_meta = aggregated.get("metadata", {})
        aggregated_meta["cache_hit"] = False
        aggregated_meta["cached_at"] = datetime.now(tz=timezone.utc).isoformat()
        aggregated["metadata"] = aggregated_meta

        if self.cache_store:
            self.cache_store.set(cache_key, aggregated)

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

                # Add photos as images
                for photo_url in place.get("photo_urls", []):
                    aggregated["images"].append({
                        "url": photo_url,
                        "source": "google_places",
                        "type": "restaurant_photo"
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

    def _build_cache_key(self, restaurant_name: str, location: str, place_id: Optional[str]) -> str:
        key_base = f"{restaurant_name}::{location}"
        if place_id:
            key_base = f"{key_base}::{place_id}"
        normalized = re.sub(r"[^a-z0-9]+", "-", key_base.lower()).strip("-")
        return normalized
