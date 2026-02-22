"""Simple local cache store for multi-source aggregation results."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cached payload with metadata."""

    cached_at: float
    ttl: int
    data: dict


class LocalCacheStore:
    """File-backed cache store with TTL."""

    def __init__(
        self,
        cache_path: Optional[Path] = None,
        default_ttl_seconds: int = 604800
    ):
        if cache_path is None:
            base_dir = Path(__file__).resolve().parents[3]
            cache_path = base_dir / ".cache" / "multi_source_cache.json"

        self.cache_path = cache_path
        self.default_ttl_seconds = default_ttl_seconds
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> Optional[CacheEntry]:
        """Get cached entry if present and not expired."""
        cache = self._load()
        entry = cache.get(key)
        if not entry:
            return None

        cached_at = float(entry.get("cached_at", 0))
        ttl = int(entry.get("ttl", self.default_ttl_seconds))
        if self._is_expired(cached_at, ttl):
            cache.pop(key, None)
            self._save(cache)
            logger.info(f"Cache expired for key: {key}")
            return None

        return CacheEntry(
            cached_at=cached_at,
            ttl=ttl,
            data=entry.get("data", {})
        )

    def set(self, key: str, data: dict, ttl: Optional[int] = None) -> None:
        """Store cache entry with TTL."""
        cache = self._load()
        cache[key] = {
            "cached_at": time.time(),
            "ttl": ttl or self.default_ttl_seconds,
            "data": data
        }
        self._save(cache)

    def _is_expired(self, cached_at: float, ttl: int) -> bool:
        return (time.time() - cached_at) > ttl

    def _load(self) -> dict:
        if not self.cache_path.exists():
            return {}
        try:
            with self.cache_path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(f"Failed to load cache file: {exc}")
            return {}

    def _save(self, cache: dict) -> None:
        try:
            with self.cache_path.open("w", encoding="utf-8") as handle:
                json.dump(cache, handle)
        except OSError as exc:
            logger.warning(f"Failed to save cache file: {exc}")
