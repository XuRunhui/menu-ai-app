"""Site-wide ceilings: what stops traffic that rotates addresses to get round per-IP limits."""

import asyncio
import hashlib
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.rate_limit import DemoCapReached, llm_budget_exhausted, reset_demo_limits
from app.main import app
from app.services import cache_service
from app.services.llm_client import LLMClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_limits():
    reset_demo_limits()
    yield
    reset_demo_limits()


def _fake_llm(replies):
    llm = LLMClient(api_key="test-key", model_name="deepseek-flash")
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        message = SimpleNamespace(content=replies.pop(0) if replies else '{"ok": true}')
        return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")], usage=None)

    llm._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return llm, calls


def test_deepseek_calls_stop_at_the_hourly_budget_but_cached_answers_are_free(monkeypatch):
    monkeypatch.setattr(settings, "demo_llm_calls_per_hour", 2)
    llm, calls = _fake_llm(['{"a": 1}', '{"b": 2}'])

    llm.generate("first prompt", json_mode=True, cache=True, purpose="test")
    llm.generate("second prompt", json_mode=True)
    assert llm_budget_exhausted()
    # The first prompt again is answered from the cache, so it needs no budget.
    assert llm.generate("first prompt", json_mode=True, cache=True, purpose="test") == '{"a": 1}'
    with pytest.raises(DemoCapReached):
        llm.generate("third prompt", json_mode=True)
    assert len(calls) == 2


def test_deepseek_calls_also_stop_at_the_daily_budget(monkeypatch):
    monkeypatch.setattr(settings, "demo_llm_calls_per_day", 1)
    llm, calls = _fake_llm(["one", "two"])
    llm.generate("daily one")
    with pytest.raises(DemoCapReached):
        llm.generate("daily two")
    assert len(calls) == 1


def test_new_menu_photos_share_one_hourly_ceiling_across_visitors(monkeypatch):
    from app import main
    from app.models.menu import ParsedMenu

    monkeypatch.setattr(settings, "demo_menus_per_hour", 2)
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    monkeypatch.setattr(main, "parse_menu_image",
                        lambda **kwargs: ParsedMenu(menu=[{"category": "Mains", "items": [{"name": "Galbi"}]}]))

    def upload(i):
        return client.post("/api/v1/menu/parse", headers={"X-Forwarded-For": f"198.51.100.{i}"},
                           files={"image": ("menu.jpg", f"photo {i}".encode(), "image/jpeg")}).status_code

    # Three different visitors (per-IP limits wouldn't stop them), one ceiling for the site.
    assert [upload(i) for i in range(3)] == [200, 200, 429]

    # A photo already read is answered from the cache and still works.
    seen = b"photo 0"
    assert cache_service.get_menu_parse(hashlib.sha256(seen).hexdigest(), None, settings.deepseek_model)
    assert client.post("/api/v1/menu/parse", files={"image": ("menu.jpg", seen, "image/jpeg")}).status_code == 200


def test_restaurant_menu_lookups_count_toward_the_same_ceiling(monkeypatch):
    from app.services.menu_sources import gather

    monkeypatch.setattr(settings, "demo_menus_per_hour", 1)
    monkeypatch.setattr(settings, "google_places_api_key", "test-key")
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    looked_up = []

    def fake_places(self, place_id):
        looked_up.append(place_id)
        return {"name": "Somewhere", "website": None}

    monkeypatch.setattr("app.services.google_places_service.GooglePlacesService.get_menu_fields", fake_places)
    first = gather.read_source("website", "ChIJ-first")
    second = gather.read_source("website", "ChIJ-second")
    assert first.report.status != "unavailable" or "menus" not in (first.report.detail or "")
    assert second.report.status == "unavailable" and "menus" in second.report.detail
    assert looked_up == ["ChIJ-first"]


def test_with_the_ai_budget_spent_no_unjudged_photo_is_cached(tmp_path, monkeypatch):
    from app.api.v1.endpoints import dish_image as endpoint
    from app.services.dish_image_service import DishImageService
    from app.services.image_sources import ImageCandidate

    monkeypatch.setattr(settings, "dish_image_judge_enabled", True)
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    monkeypatch.setattr(settings, "demo_llm_calls_per_hour", 1)
    service = DishImageService(images_dir=tmp_path, providers=[
        ("fake", lambda q, n: [ImageCandidate("https://img.test/a.jpg", "duckduckgo", 800)], 1)])
    service._download_bytes = lambda url: b"\xff\xd8\xff" + b"0" * 4096
    llm, _ = _fake_llm([])
    monkeypatch.setattr(service, "_judge_client", lambda: llm)
    monkeypatch.setattr(endpoint, "get_dish_image_service", lambda: service)
    llm.generate("spend the only call")

    response = client.get("/api/v1/dish-image", params={"dish_name": "Budget Soup", "restaurant_name": "Budget"})
    assert response.status_code == 429                          # the page asks again later
    assert cache_service.get_image("Budget", "Budget Soup") is None
    assert not cache_service.recent_image_failure("Budget", "Budget Soup")


def test_combos_made_without_the_model_are_not_cached(monkeypatch):
    from app.api.v1.endpoints import knowledge as knowledge_api
    from app.models.knowledge import ComboRequest, ComboResponse

    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    monkeypatch.setattr(settings, "demo_llm_calls_per_hour", 1)
    llm, _ = _fake_llm([])
    llm.generate("spend the only call")
    monkeypatch.setattr(knowledge_api, "compute_combos", lambda request: ComboResponse(
        combos=[{"dishes": ["A", "B"], "score": 0.5, "title": "Keyword pair", "explanation": "x", "tip": "y",
                 "pairings": [], "shared_compounds": [], "sources": []}], knowledge_available=True, cuisine="K"))
    body = {"dishes": [{"name": "Budget A"}, {"name": "Budget B"}]}
    assert client.post("/api/v1/knowledge/combos", json=body).status_code == 200
    assert cache_service.get_llm_response(knowledge_api.combo_cache_key(ComboRequest(**body))) is None


def test_google_places_requests_stop_at_the_daily_budget(monkeypatch):
    from app.services.google_places_service import GooglePlacesService

    monkeypatch.setattr(settings, "demo_places_calls_per_day", 1)
    sent = []

    class Reply:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"status": "OK", "result": {"place_id": "p", "name": "N", "website": None}}

    monkeypatch.setattr("app.services.google_places_service.requests.get",
                        lambda *args, **kwargs: sent.append(args) or Reply())
    service = GooglePlacesService("test-key")
    service.get_menu_fields("ChIJ-one")
    with pytest.raises(DemoCapReached):
        service.get_menu_fields("ChIJ-two")
    assert len(sent) == 1

    # Through the API the refusal is a 429, not a server error.
    monkeypatch.setattr(settings, "google_places_api_key", "test-key")
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    assert client.get("/api/v1/places/ChIJ-three").status_code == 429
