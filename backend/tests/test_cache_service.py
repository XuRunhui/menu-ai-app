"""Tests for the database-backed caches."""

import json
from datetime import timedelta

import numpy as np
from sqlalchemy import select

from app.db.models import ImageCache, ImageSearchFailure, LLMCache, RequestLog, WebSearchCache
from app.db.session import SessionLocal
from app.services import cache_service


def _age(model, key_column, key, delta, time_column):
    with SessionLocal() as db:
        row = db.scalar(select(model).where(key_column == key))
        setattr(row, time_column, getattr(row, time_column) - delta)
        db.commit()


def test_llm_cache_roundtrip_and_expiry():
    cache_service.set_llm_response("k-llm", "deepseek-flash", "test", "hello", 10, 2)
    assert cache_service.get_llm_response("k-llm") == "hello"

    _age(LLMCache, LLMCache.key, "k-llm", cache_service.LLM_TTL + timedelta(days=1), "created_at")
    assert cache_service.get_llm_response("k-llm") is None


def test_embedding_cache_roundtrip_keeps_dimensions_separate():
    vector = np.arange(4, dtype=np.float32)
    cache_service.set_embeddings("model-x", 4, {"spicy ramen": vector})

    found = cache_service.get_embeddings("model-x", 4, ["spicy ramen", "unknown"])
    assert set(found) == {"spicy ramen"}
    assert np.allclose(found["spicy ramen"], vector)
    assert cache_service.get_embeddings("model-x", 384, ["spicy ramen"]) == {}


def test_web_search_cache_is_case_insensitive_and_expires():
    cache_service.set_web_search("Tofu House", "Koreatown", {"reviews": [{"text": "great"}], "images": []})
    payload, _cached_at = cache_service.get_web_search("tofu house", "KOREATOWN")
    assert payload["reviews"][0]["text"] == "great"

    key = cache_service.web_search_key("Tofu House", "Koreatown")
    _age(WebSearchCache, WebSearchCache.key, key, cache_service.WEB_SEARCH_TTL + timedelta(hours=1), "cached_at")
    assert cache_service.get_web_search("Tofu House", "Koreatown") is None


def test_image_failure_is_remembered_briefly_and_cleared_by_success():
    cache_service.record_image_failure("Kroft", "Cubano", "rate limited")
    assert cache_service.recent_image_failure("Kroft", "Cubano") is True

    cache_service.set_image("Kroft", "Cubano", "Kroft Cubano food", "abc.jpg", "https://img.test/a.jpg")
    assert cache_service.recent_image_failure("Kroft", "Cubano") is False
    assert cache_service.get_image("kroft", "cubano").filename == "abc.jpg"


def test_a_rejected_dish_is_remembered_for_days_and_an_empty_search_for_minutes():
    cache_service.record_image_failure("Ttl", "Mystery Plate", cache_service.NO_MATCHING_PHOTO)
    cache_service.record_image_failure("Ttl", "Blank Search", "search found nothing")
    for dish in ("Mystery Plate", "Blank Search"):
        _age(ImageSearchFailure, ImageSearchFailure.key, cache_service.image_key("Ttl", dish),
             timedelta(hours=1), "failed_at")

    cache_service.purge_expired()
    assert cache_service.recent_image_failure("Ttl", "Mystery Plate") is True
    assert cache_service.recent_image_failure("Ttl", "Blank Search") is False

    _age(ImageSearchFailure, ImageSearchFailure.key, cache_service.image_key("Ttl", "Mystery Plate"),
         cache_service.IMAGE_NO_MATCH_TTL, "failed_at")
    assert cache_service.recent_image_failure("Ttl", "Mystery Plate") is False


def test_a_dish_photo_can_be_found_by_dish_name_alone():
    cache_service.set_image("Named Place", "보쌈 / BOSSAM", "q", "named.jpg", "https://img.test/n.jpg")
    assert cache_service.get_image_for_dish(" 보쌈 / bossam ").filename == "named.jpg"
    assert cache_service.get_image_for_dish("Jokbal") is None


def test_purge_removes_expired_rows():
    cache_service.set_image("Purge", "Old Dish", "q", "old.jpg", "https://img.test/old.jpg")
    key = cache_service.image_key("Purge", "Old Dish")
    _age(ImageCache, ImageCache.key, key, cache_service.IMAGE_TTL + timedelta(days=1), "cached_at")

    cache_service.purge_expired()
    with SessionLocal() as db:
        assert db.get(ImageCache, key) is None


def test_request_log_write():
    cache_service.log_request("GET", "/api/test-log", 200, 12.3, None, {"calls": 2, "cache_hits": 1,
                                                                        "prompt_tokens": 50, "completion_tokens": 7})
    with SessionLocal() as db:
        row = db.scalar(select(RequestLog).where(RequestLog.path == "/api/test-log"))
    assert (row.llm_calls, row.llm_cache_hits, row.llm_prompt_tokens) == (2, 1, 50)


def test_legacy_json_image_cache_import(tmp_path, monkeypatch):
    (tmp_path / "dish_images").mkdir()
    (tmp_path / "dish_images" / "legacy.jpg").write_bytes(b"\xff\xd8\xff" + b"0" * 2000)
    (tmp_path / "dish_image_db.json").write_text(json.dumps({
        "x": {"filename": "legacy.jpg", "dish": "Legacy Dish", "restaurant": "Old Place",
              "source_url": "https://img.test/l.jpg", "cached_at": 1_900_000_000},
        "missing-file": {"filename": "gone.jpg", "dish": "Gone", "restaurant": "", "cached_at": 1_900_000_000},
    }))
    with SessionLocal() as db:  # importer only runs into an empty table
        db.query(ImageCache).delete()
        db.commit()

    assert cache_service.import_legacy_json_caches(tmp_path) == 1
    assert cache_service.get_image("Old Place", "Legacy Dish").filename == "legacy.jpg"
