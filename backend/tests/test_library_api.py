"""Guest mode (default): shared parse cache, public menu restore, Google photo proxy.
Accounts mode (AUTH_ENABLED): per-user library and restaurant history."""

import itertools

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import app.main as main_module
from app.api.v1.endpoints import google_places as places_module
from app.core.config import settings
from app.db.models import RequestLog
from app.db.session import SessionLocal
from app.models.menu import MenuCategory, MenuItem, ParsedMenu

_usernames = (f"libuser{i}" for i in itertools.count())
_images = (b"\x89PNG\r\n\x1a\n" + f"menu-{i}".encode() for i in itertools.count())


@pytest.fixture()
def parse_calls(monkeypatch):
    calls = []

    def fake_parse(image_source, api_key, target_language=None, model_name=None):
        calls.append(target_language)
        return ParsedMenu(detected_language="English", target_language=target_language, menu=[
            MenuCategory(category="Mains", items=[MenuItem(name="Ramen", price=12.0, description="Spicy")])
        ])

    monkeypatch.setattr(main_module, "parse_menu_image", fake_parse)
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    return calls


@pytest.fixture()
def accounts_on(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)


def _client(signed_in: bool = False) -> TestClient:
    client = TestClient(main_module.app)
    if signed_in:
        response = client.post("/api/v1/auth/register", json={"username": next(_usernames), "password": "correct horse"})
        assert response.status_code == 201
    return client


def _parse(client, image, language=None, restaurant="The Kroft"):
    data = {"restaurant_name": restaurant} if restaurant else {}
    if language:
        data["target_language"] = language
    return client.post("/api/v1/menu/parse", files={"image": ("menu.png", image, "image/png")}, data=data)


# ─── Guest mode ─────────────────────────────────────────────────────────────────


def test_guest_parse_is_shared_cached_and_restorable(parse_calls):
    image = next(_images)
    first = _parse(_client(), image, restaurant=None).json()
    assert isinstance(first["menu_id"], str) and len(first["menu_id"]) == 32

    # A different visitor uploading the same image gets the cached result.
    second = _parse(_client(), image, restaurant="The Kroft").json()
    assert second["menu_id"] == first["menu_id"]
    assert len(parse_calls) == 1

    translated = _parse(_client(), image, language="Chinese").json()
    assert translated["menu_id"] != first["menu_id"]
    assert len(parse_calls) == 2

    restored = _client().get(f"/api/v1/menus/{first['menu_id']}").json()
    assert restored["restaurant_name"] == "The Kroft"  # label added by the second upload
    assert restored["parsed_menu"]["menu"][0]["items"][0]["name"] == "Ramen"
    assert restored["parsed_menu"]["menu_id"] == first["menu_id"]


def test_unknown_menu_id_is_404():
    assert _client().get("/api/v1/menus/0123456789abcdef0123456789abcdef").status_code == 404


def test_account_routes_are_off_in_guest_mode(parse_calls):
    client = _client()
    assert client.get("/api/v1/auth/config").json()["auth_enabled"] is False
    assert client.post("/api/v1/auth/register", json={"username": "someone", "password": "correct horse"}).status_code == 404
    assert client.get("/api/v1/me/menus").status_code == 404


def test_google_place_photos_are_never_requested_or_served(monkeypatch):
    # Place photos were dropped: they cost a billed request each and Google requires crediting the
    # photographer wherever one is shown. Nothing may ask for them or hand them to the browser.
    import requests as requests_module

    sent = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self.payload

    def fake_get(url, params=None, **kwargs):
        sent.append((url, dict(params or {})))
        if "textsearch" in url:
            return FakeResponse({"status": "OK", "results": [{
                "place_id": "p1", "name": "Kroft", "formatted_address": "Anaheim",
                "photos": [{"photo_reference": "PhotoRef_123-abc", "width": 4000, "height": 3000}]}]})
        return FakeResponse({"status": "OK", "result": {"place_id": "p1", "name": "Kroft"}})

    from app.services import google_places_service

    monkeypatch.setattr(google_places_service.requests, "get", fake_get)
    service = google_places_service.GooglePlacesService("AIzaSECRET")

    results = service.search_places("kroft", use_exact_match=False)["results"]
    assert "photos" not in results[0]                      # stripped before anything sees it
    service.get_place_details("p1")
    service.get_menu_fields("p1")

    # The old photo proxy address is now just an (invalid) place id, never an image.
    response = _client().get("/api/v1/places/photo", params={"ref": "PhotoRef_123-abc"})
    assert not response.headers.get("content-type", "").startswith("image/")

    assert not any("/place/photo" in url for url, _ in sent)
    assert not any("photos" in params.get("fields", "") for _, params in sent)
def test_api_requests_are_logged(parse_calls):
    _parse(_client(), next(_images))
    with SessionLocal() as db:
        row = db.scalar(select(RequestLog).where(RequestLog.path == "/api/v1/menu/parse").order_by(RequestLog.id.desc()))
    assert row is not None and row.status_code == 200 and row.duration_ms >= 0


# ─── Accounts mode ──────────────────────────────────────────────────────────────


def test_signed_in_parse_is_added_to_library(parse_calls, accounts_on):
    client = _client(signed_in=True)
    menu_id = _parse(client, next(_images)).json()["menu_id"]

    menus = client.get("/api/v1/me/menus").json()
    assert menus[0]["menu_id"] == menu_id and menus[0]["restaurant_name"] == "The Kroft"

    other = _client(signed_in=True)
    assert other.get("/api/v1/me/menus").json() == []
    assert other.get(f"/api/v1/me/menus/{menus[0]['id']}").status_code == 404
    assert client.delete(f"/api/v1/me/menus/{menus[0]['id']}").status_code == 204
    assert client.get("/api/v1/me/menus").json() == []


def test_restaurant_views_are_recorded_for_signed_in_users(monkeypatch, accounts_on):
    class FakePlaces:
        def __init__(self, key):
            pass

        def get_full_place_data(self, place_id):
            return {"place": {"place_id": place_id, "name": "Kroft", "formatted_address": "Anaheim"}, "reviews": []}

    monkeypatch.setattr(places_module, "GooglePlacesService", FakePlaces)
    monkeypatch.setattr(settings, "google_places_api_key", "test-key")
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")

    client = _client(signed_in=True)
    client.get("/api/v1/places/place-1", params={"label": "the kroft anaheim"})
    client.get("/api/v1/places/place-2", params={"label": "tofu house"})
    client.get("/api/v1/places/place-1", params={"label": "the kroft"})

    history = client.get("/api/v1/me/restaurants").json()
    assert [h["place_id"] for h in history] == ["place-1", "place-2"]
    assert history[0]["label"] == "the kroft"


def test_place_search_reports_google_errors(monkeypatch):
    class DeniedPlaces:
        def __init__(self, key):
            pass

        def search_places(self, query, use_exact_match=True):
            return {"results": [], "status": "REQUEST_DENIED",
                    "error_message": "This API key is not authorized to use this service or API."}

    monkeypatch.setattr(places_module, "GooglePlacesService", DeniedPlaces)
    monkeypatch.setattr(settings, "google_places_api_key", "restricted-key")

    response = _client().post("/api/v1/places/search", json={"query": "bcd tofu house"})
    assert response.status_code == 502
    assert "REQUEST_DENIED" in response.json()["detail"]
    assert "not authorized" in response.json()["detail"]
