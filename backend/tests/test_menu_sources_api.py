"""Tests for the menu-source endpoints the results page calls."""

from fastapi.testclient import TestClient

from app.main import app
from app.models.menu_sources import SourceReport, SourceResult
from app.core.rate_limit import reset_demo_limits

client = TestClient(app)


def _menu(*names):
    return {"detected_language": "English", "menu": [
        {"category": "Menu", "items": [{"name": n, "price": 10.0} for n in names]}]}


def test_combine_merges_what_the_browser_sends_back():
    response = client.post("/api/v1/menus/combine", json={
        "sources": [{"kind": "website", "menu": _menu("Galbi", "Bulgogi")},
                    {"kind": "upload", "menu": _menu("Galbi", "Naengmyeon")}],
        "review_dishes": [{"name": "Yukhoe", "mention_count": 2}],
    })
    assert response.status_code == 200
    body = response.json()
    items = {i["name"]: i for c in body["menu"]["menu"] for i in c["items"]}
    assert items["Galbi"]["sources"] == ["upload", "website"]
    assert items["Yukhoe"]["sources"] == ["reviews"]
    assert body["total_items"] == 4 and body["suggest_upload"] is False


def test_combine_with_nothing_is_an_empty_menu_that_asks_for_a_photo():
    body = client.post("/api/v1/menus/combine", json={}).json()
    assert body["total_items"] == 0 and body["suggest_upload"] is True


def test_a_source_is_read_by_kind(monkeypatch):
    reset_demo_limits()
    seen = []

    def fake(kind, place_id, target_language="English", place=None):
        seen.append((kind, place_id, target_language))
        return SourceResult(report=SourceReport(kind=kind, status="none", detail="Nothing there."))

    monkeypatch.setattr("app.api.v1.endpoints.menu_sources.read_source", fake)
    response = client.post("/api/v1/menus/sources/website",
                           json={"place_id": "ChIJ-test-place", "target_language": "Chinese"})
    assert response.status_code == 200 and response.json()["report"]["detail"] == "Nothing there."
    assert seen == [("website", "ChIJ-test-place", "Chinese")]


def test_only_known_sources_can_be_read():
    assert client.post("/api/v1/menus/sources/yelp", json={"place_id": "ChIJ-test"}).status_code == 422
