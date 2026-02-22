"""Dish image service: search, download, and cache per-dish images via DuckDuckGo."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class DishImageService:
    """Fetch dish-specific images from DuckDuckGo and cache them locally.

    Cache strategy:
    - Images are stored in ``{backend_root}/.cache/dish_images/`` as files.
    - A JSON sidecar DB at ``{backend_root}/.cache/dish_image_db.json`` maps
      ``restaurant::dish`` keys to filenames + metadata.
    - TTL is 28 days (images rarely change; can be invalidated manually).
    - Check DB before any network call — first cache hit is O(1) JSON read.
    """

    IMAGE_TTL_SECONDS: int = 60 * 60 * 24 * 28   # 28 days
    DOWNLOAD_TIMEOUT: int = 10                      # seconds per attempt
    MAX_SEARCH_RESULTS: int = 5                     # how many DDGS results to try

    def __init__(
        self,
        images_dir: Optional[Path] = None,
        db_path: Optional[Path] = None,
    ) -> None:
        base = Path(__file__).resolve().parents[2]   # → backend/
        self.images_dir = images_dir or (base / ".cache" / "dish_images")
        self.db_path = db_path or (base / ".cache" / "dish_image_db.json")
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    # ── Cache key / filename helpers ─────────────────────────────────────────

    def _make_key(self, restaurant_name: str, dish_name: str) -> str:
        """Stable MD5 key from normalised restaurant + dish names."""
        normalised = f"{restaurant_name.strip().lower()}::{dish_name.strip().lower()}"
        return hashlib.md5(normalised.encode("utf-8")).hexdigest()

    def _filename_from_key(self, key: str, ext: str = ".jpg") -> str:
        return f"{key}{ext}"

    # ── JSON sidecar DB ───────────────────────────────────────────────────────

    def _load_db(self) -> dict:
        if not self.db_path.exists():
            return {}
        try:
            with self.db_path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("dish_image_db: failed to load (%s)", exc)
            return {}

    def _save_db(self, db: dict) -> None:
        try:
            with self.db_path.open("w", encoding="utf-8") as fh:
                json.dump(db, fh)
        except OSError as exc:
            logger.warning("dish_image_db: failed to save (%s)", exc)

    # ── Public API ────────────────────────────────────────────────────────────

    def get_cached_filename(self, restaurant_name: str, dish_name: str) -> Optional[str]:
        """Return the cached image filename if present, valid, and not expired.

        Args:
            restaurant_name: Restaurant name used as part of the cache key.
            dish_name: Dish name used as part of the cache key.

        Returns:
            Filename string (e.g. ``"abc123.jpg"``) or ``None`` if no valid
            cache entry exists.
        """
        key = self._make_key(restaurant_name, dish_name)
        db = self._load_db()
        entry = db.get(key)
        if not entry:
            return None

        # TTL check
        if time.time() - float(entry.get("cached_at", 0)) > self.IMAGE_TTL_SECONDS:
            logger.debug("dish_image_db: TTL expired for key %s", key)
            return None

        filename = entry.get("filename")
        if filename and (self.images_dir / filename).exists():
            return filename

        return None

    async def fetch_and_cache(
        self, restaurant_name: str, dish_name: str
    ) -> Optional[str]:
        """Search DuckDuckGo for a dish image, download the first usable result,
        save it locally, and record it in the DB.

        Args:
            restaurant_name: Restaurant name (e.g. ``"BCD Tofu House"``).
            dish_name: Dish name (e.g. ``"Soon Tofu Jjigae"``).

        Returns:
            The saved filename (relative to ``images_dir``) or ``None`` if all
            attempts fail.
        """
        from duckduckgo_search import DDGS

        # Build query — omit empty restaurant_name to avoid leading space
        parts = [p for p in [restaurant_name.strip(), dish_name.strip(), "food"] if p]
        query = " ".join(parts)
        logger.info("dish_image: searching DDGS for '%s'", query)

        try:
            ddgs = DDGS()
            results: list[dict] = await asyncio.to_thread(
                lambda: list(
                    ddgs.images(
                        keywords=query,
                        max_results=self.MAX_SEARCH_RESULTS,
                        type_image="photo",
                    )
                )
            )
        except Exception as exc:
            logger.error("dish_image: DDGS search failed for '%s': %s", dish_name, exc)
            return None

        if not results:
            logger.info("dish_image: no results found for '%s'", dish_name)
            return None

        key = self._make_key(restaurant_name, dish_name)

        for result in results:
            image_url: Optional[str] = result.get("image")
            if not image_url:
                continue

            # Determine file extension from URL (fall back to .jpg)
            ext = ".jpg"
            clean_url = image_url.lower().split("?")[0]
            for candidate in (".png", ".webp", ".jpeg", ".jpg"):
                if clean_url.endswith(candidate):
                    ext = ".jpg" if candidate == ".jpeg" else candidate
                    break

            filename = self._filename_from_key(key, ext)
            filepath = self.images_dir / filename

            try:
                content: bytes = await asyncio.to_thread(
                    self._download_bytes, image_url
                )
            except Exception as exc:
                logger.warning(
                    "dish_image: download failed for %s: %s", image_url, exc
                )
                continue

            # Sanity check: must be at least 1 KB to be a real image
            if len(content) < 1024:
                logger.debug("dish_image: result too small, skipping %s", image_url)
                continue

            # Persist file
            try:
                filepath.write_bytes(content)
            except OSError as exc:
                logger.error("dish_image: failed to write file %s: %s", filepath, exc)
                continue

            # Update DB
            db = self._load_db()
            db[key] = {
                "filename": filename,
                "source_url": image_url,
                "restaurant": restaurant_name,
                "dish": dish_name,
                "cached_at": time.time(),
            }
            self._save_db(db)

            logger.info(
                "dish_image: cached '%s' → %s (%d bytes)",
                dish_name, filename, len(content),
            )
            return filename

        logger.warning(
            "dish_image: all download attempts failed for '%s' at '%s'",
            dish_name, restaurant_name,
        )
        return None

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _download_bytes(url: str) -> bytes:
        """Synchronous HTTP GET for running in a thread pool."""
        resp = requests.get(
            url,
            timeout=DishImageService.DOWNLOAD_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (compatible; MenuAI/1.0)"},
            allow_redirects=True,
        )
        resp.raise_for_status()
        return resp.content


# ── Module-level singleton ────────────────────────────────────────────────────

_service: Optional[DishImageService] = None


def get_dish_image_service() -> DishImageService:
    """Return (or lazily create) the application-scoped DishImageService."""
    global _service
    if _service is None:
        _service = DishImageService()
    return _service
