"""The dish-image endpoint: only real searches count toward a visitor's hourly limit."""

from fastapi.testclient import TestClient

from app.api.v1.endpoints import dish_image as endpoint
from app.core.config import settings
from app.core.rate_limit import reset_demo_limits
from app.main import app
from app.services import cache_service
from app.services.dish_image_service import DishImageService

client = TestClient(app)


def _service(tmp_path, monkeypatch):
    """A service whose searches find nothing, and a list of the dishes it was asked to search."""
    searched = []
    service = DishImageService(images_dir=tmp_path, providers=[])

    async def fake_fetch(restaurant, dish, translated="", description=""):
        searched.append(dish)
        return None

    service.fetch_and_cache = fake_fetch
    monkeypatch.setattr(endpoint, "get_dish_image_service", lambda: service)
    return searched


def _get(dish, restaurant):
    return client.get("/api/v1/dish-image", params={"dish_name": dish, "restaurant_name": restaurant})


def test_cached_photos_do_not_use_up_the_search_limit(tmp_path, monkeypatch):
    reset_demo_limits()
    monkeypatch.setattr(settings, "demo_dish_image_rate_limit_per_hour", 2)
    searched = _service(tmp_path, monkeypatch)
    (tmp_path / "bossam.jpg").write_bytes(b"\xff\xd8\xff" + b"0" * 2048)
    cache_service.set_image("Limit House", "Bossam", "Bossam food", "bossam.jpg", "https://img.test/b.jpg")

    # A results page asks again every time it re-renders; answering from the cache is free.
    for _ in range(5):
        response = _get("Bossam", "Limit House")
        assert response.status_code == 200
        assert response.json()["image_url"].endswith("/dish-images/bossam.jpg")

    # So the visitor's two searches are all still there, and only the third is refused.
    statuses = [_get(dish, "Limit House").status_code for dish in ("Kalbi", "Japchae", "Mandu")]
    assert statuses == [200, 200, 429]
    assert searched == ["Kalbi", "Japchae"]


def test_a_menu_without_a_restaurant_name_reuses_a_photo_chosen_elsewhere(tmp_path, monkeypatch):
    # The same menu uploaded again without its name used to search every dish again.
    reset_demo_limits()
    searched = _service(tmp_path, monkeypatch)
    (tmp_path / "kobawoo-bossam.jpg").write_bytes(b"\xff\xd8\xff" + b"0" * 2048)
    cache_service.set_image("Kobawoo House", "보쌈 / BOSSAM", "q", "kobawoo-bossam.jpg",
                            "https://img.test/k.jpg", source="duckduckgo")

    body = _get("보쌈 / BOSSAM", "").json()
    assert body["image_url"].endswith("/dish-images/kobawoo-bossam.jpg")
    assert body["cached"] is True and body["source"] == "duckduckgo"
    assert searched == []

    # Another restaurant's dish of the same name gets its own search, which can find its own photo.
    _get("보쌈 / BOSSAM", "Another Korean Place")
    assert searched == ["보쌈 / BOSSAM"]


def test_a_dish_that_just_failed_is_answered_without_counting(tmp_path, monkeypatch):
    reset_demo_limits()
    monkeypatch.setattr(settings, "demo_dish_image_rate_limit_per_hour", 1)
    searched = _service(tmp_path, monkeypatch)
    cache_service.record_image_failure("Limit House 2", "Sundae", "no usable image")

    for _ in range(3):
        response = _get("Sundae", "Limit House 2")
        assert response.status_code == 200 and response.json()["image_url"] is None

    assert _get("Soondubu", "Limit House 2").status_code == 200
    assert searched == ["Soondubu"]


# ─── The same rule for the other endpoints: repeats of finished work are free ───


def test_a_menu_photo_read_before_does_not_count_toward_the_limit(monkeypatch):
    import hashlib

    from app import main
    from app.models.menu import ParsedMenu

    reset_demo_limits()
    monkeypatch.setattr(settings, "demo_rate_limit_per_hour", 1)
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    reads = []

    def fake_parse(**kwargs):
        reads.append(kwargs["image_source"])
        return ParsedMenu(menu=[{"category": "Mains", "items": [{"name": "Galbi"}]}])

    monkeypatch.setattr(main, "parse_menu_image", fake_parse)
    sample = b"\xff\xd8\xff sample menu photo"
    cache_service.set_menu_parse(hashlib.sha256(sample).hexdigest(), None, settings.deepseek_model, "Sample",
                                 "English", 1, {"menu": [{"category": "Mains", "items": [{"name": "Poutine"}]}]})

    def upload(content):
        return client.post("/api/v1/menu/parse", files={"image": ("menu.jpg", content, "image/jpeg")})

    # The sample menu, tried again and again, is answered from the cache every time.
    assert [upload(sample).status_code for _ in range(4)] == [200, 200, 200, 200]
    # A new photo is real work: the first is read, the second is over this visitor's limit.
    assert [upload(b"\xff\xd8\xff new photo 1").status_code, upload(b"\xff\xd8\xff new photo 2").status_code] == [200, 429]
    assert len(reads) == 1


def test_cached_combos_do_not_count_toward_the_limit(monkeypatch):
    from app.api.v1.endpoints import knowledge as knowledge_api
    from app.models.knowledge import ComboRequest, ComboResponse

    reset_demo_limits()
    monkeypatch.setattr(settings, "demo_rate_limit_per_hour", 1)
    seeded = {"dishes": [{"name": "Seed A"}, {"name": "Seed B"}], "restaurant_name": "Seeded"}
    cache_service.set_llm_response(knowledge_api.combo_cache_key(ComboRequest(**seeded)), "m", "combo_response",
                                   ComboResponse(combos=[], knowledge_available=True, cuisine="Seeded").model_dump_json())
    monkeypatch.setattr(knowledge_api, "compute_combos",
                        lambda request: ComboResponse(combos=[], knowledge_available=True, cuisine="New"))

    assert [client.post("/api/v1/knowledge/combos", json=seeded).json()["cuisine"] for _ in range(3)] == ["Seeded"] * 3
    fresh = [client.post("/api/v1/knowledge/combos", json={"dishes": [{"name": f"New {i}"}, {"name": "X"}]}).status_code
             for i in range(2)]
    assert fresh == [200, 429]


# ─── Who counts as a visitor, and what one request may ask for ───────────────


def test_a_visitor_cannot_dodge_the_limit_by_sending_their_own_forwarded_header(tmp_path, monkeypatch):
    # Cloud Run appends the real address on the right; anything to its left is the client's own.
    reset_demo_limits()
    monkeypatch.setattr(settings, "demo_dish_image_rate_limit_per_hour", 2)
    _service(tmp_path, monkeypatch)

    def search(dish, fake):
        return client.get("/api/v1/dish-image", params={"dish_name": dish, "restaurant_name": "Spoof"},
                          headers={"X-Forwarded-For": f"{fake}, 198.51.100.7"}).status_code

    assert [search(f"Dish {i}", f"203.0.113.{i}") for i in range(3)] == [200, 200, 429]


def test_dish_photo_searches_have_a_daily_ceiling_across_visitors(tmp_path, monkeypatch):
    reset_demo_limits()
    monkeypatch.setattr(settings, "demo_dish_image_daily_cap", 2)
    _service(tmp_path, monkeypatch)
    statuses = [client.get("/api/v1/dish-image", params={"dish_name": f"Daily {i}", "restaurant_name": "Cap"},
                           headers={"X-Forwarded-For": f"198.51.100.{i}"}).status_code for i in range(3)]
    assert statuses == [200, 200, 429]


def test_combining_refuses_more_dishes_than_any_menu_has():
    from app.models.menu_sources import MAX_COMBINED_DISHES

    reset_demo_limits()
    items = [{"name": f"Dish {i}"} for i in range(MAX_COMBINED_DISHES + 1)]
    oversized = {"sources": [{"kind": "upload", "menu": {"menu": [{"category": "All", "items": items}]}}]}
    assert client.post("/api/v1/menus/combine", json=oversized).status_code == 422

    long_name = {"sources": [{"kind": "upload", "menu": {"menu": [{"category": "All", "items": [{"name": "x" * 5000}]}]}}]}
    assert client.post("/api/v1/menus/combine", json=long_name).status_code == 422

    normal = {"sources": [{"kind": "upload", "menu": {"menu": [{"category": "All", "items": items[:60]}]}}]}
    assert client.post("/api/v1/menus/combine", json=normal).status_code == 200


def test_the_taste_prediction_takes_only_a_menu_sized_description():
    reset_demo_limits()
    response = client.post("/api/v1/recommendation/taste-texture",
                           json={"dish_name": "Soup", "description": "spicy " * 1000})
    assert response.status_code == 422
