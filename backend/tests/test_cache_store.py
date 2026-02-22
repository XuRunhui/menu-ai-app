"""Unit tests for LocalCacheStore."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.data_collection import cache_store as cache_store_module  # noqa: E402


def test_cache_store_roundtrip(tmp_path):
    """Cache store persists and returns data."""
    cache_path = tmp_path / "cache.json"
    store = cache_store_module.LocalCacheStore(cache_path=cache_path, default_ttl_seconds=10)
    store.set("key", {"value": 123})

    entry = store.get("key")
    assert entry is not None
    assert entry.data["value"] == 123


def test_cache_store_expiry(tmp_path, monkeypatch):
    """Expired cache entries are ignored."""
    cache_path = tmp_path / "cache.json"
    store = cache_store_module.LocalCacheStore(cache_path=cache_path, default_ttl_seconds=1)

    monkeypatch.setattr(cache_store_module.time, "time", lambda: 1000.0)
    store.set("key", {"value": 123})

    monkeypatch.setattr(cache_store_module.time, "time", lambda: 1002.0)
    assert store.get("key") is None
