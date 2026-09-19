"""Tests for dish image search: request coalescing, failure memory, and rate-limit retries."""

import asyncio

from app.services import cache_service
from app.services.dish_image_service import DishImageService
from app.services.image_sources import ImageCandidate, build_queries, core_dish_name, food_keyword

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 4096


class RatelimitException(Exception):
    pass


def _candidates(*urls, source="duckduckgo", width=800):
    return [ImageCandidate(url=url, source=source, width=width) for url in urls]


def _service(tmp_path, search, download=lambda url: JPEG, providers=None):
    """Service with one fake provider by default (query_limit 2 mirrors DuckDuckGo)."""
    service = DishImageService(images_dir=tmp_path,
                               providers=providers if providers is not None else [("fake", search, 2)])
    service.SEARCH_RETRY_DELAYS = (0.01, 0.01)
    service._download_bytes = download
    return service


def test_concurrent_requests_share_one_search(tmp_path):
    calls = []

    def search(query, max_results):
        calls.append(query)
        return _candidates("https://img.test/dish.jpg")

    service = _service(tmp_path, search)

    async def run():
        return await asyncio.gather(*[service.fetch_and_cache("Coalesce", "Ramen") for _ in range(5)])

    results = asyncio.run(run())
    assert len(calls) == 1
    assert len(set(results)) == 1 and results[0].endswith(".jpg")
    assert service.get_cached_filename("Coalesce", "Ramen") == results[0]


def test_failed_search_is_not_repeated(tmp_path):
    calls = []

    def search(query, max_results):
        calls.append(query)
        raise RuntimeError("network down")

    service = _service(tmp_path, search)
    assert asyncio.run(service.fetch_and_cache("Failing", "Soup")) is None
    # Two queries on the first attempt (with the restaurant, then the dish alone), then nothing:
    # the failure is remembered, so a page full of cards doesn't keep hitting the search engine.
    assert asyncio.run(service.fetch_and_cache("Failing", "Soup")) is None
    assert calls == ["Failing Soup food", "Soup food"]
    assert cache_service.recent_image_failure("Failing", "Soup")


def test_rate_limit_is_retried(tmp_path):
    attempts = []

    def search(query, max_results):
        attempts.append(query)
        if len(attempts) < 3:
            raise RatelimitException("202 Ratelimit")
        return _candidates("https://img.test/ok.jpg")

    service = _service(tmp_path, search)
    assert asyncio.run(service.fetch_and_cache("Retry", "Noodles")) is not None
    assert len(attempts) == 3


def test_duckduckgo_saying_no_results_is_asked_again(tmp_path):
    # How DuckDuckGo throttles a busy searcher; from Google Cloud, asking again 2-5 s later worked.
    attempts = []

    def search(query, max_results):
        attempts.append(query)
        if len(attempts) == 1:
            raise RuntimeError("No results found.")
        return _candidates("https://img.test/ok.jpg")

    service = _service(tmp_path, search)
    assert asyncio.run(service.fetch_and_cache("Throttled", "Bibimbap")) is not None
    assert attempts == ["Throttled Bibimbap food", "Throttled Bibimbap food"]


def test_duckduckgo_search_never_falls_back_to_another_engine(monkeypatch):
    # ddgs's default backend answers from Bing when DuckDuckGo fails, which hid a broken DuckDuckGo
    # on the live site for three deploys. The search has to ask DuckDuckGo and nothing else.
    import ddgs

    calls = {}

    class FakeDDGS:
        def __init__(self, **kwargs):
            pass

        def images(self, query, **kwargs):
            calls.update(kwargs, query=query)
            return [{"image": "https://img.test/a.jpg", "width": 800}]

    monkeypatch.setattr(ddgs, "DDGS", FakeDDGS)
    from app.services.image_sources import search_duckduckgo

    assert [c.url for c in search_duckduckgo("Bibimbap food", 5)] == ["https://img.test/a.jpg"]
    assert calls["backend"] == "duckduckgo" and calls["query"] == "Bibimbap food"


def test_non_image_downloads_are_skipped(tmp_path):
    def search(query, max_results):
        return _candidates("https://img.test/page.jpg", "https://img.test/real.png")

    def download(url):
        return b"<html>" + b"x" * 5000 if "page" in url else b"\x89PNG\r\n\x1a\n" + b"0" * 5000

    service = _service(tmp_path, search, download)
    assert asyncio.run(service.fetch_and_cache("Html", "Tacos")).endswith(".png")


def test_query_keyword_matches_the_dish_name_script():
    # "<chinese dish> food" returns unrelated pictures; the keyword must match the script.
    assert food_keyword("烤牛排套餐") == "美食"
    assert food_keyword("순두부찌개") == "음식"
    assert food_keyword("ラーメン") == "料理"
    assert food_keyword("Classic Poutine") == "food"
    assert build_queries("BCD Tofu House", "石锅拌饭") == ["BCD Tofu House 石锅拌饭 美食", "石锅拌饭 美食"]
    assert build_queries("", "Cubano") == ["Cubano food"]


def test_falls_back_to_the_dish_alone_when_the_restaurant_query_finds_nothing(tmp_path):
    queries = []

    def search(query, max_results):
        queries.append(query)
        return [] if "Unknown Diner" in query else _candidates("https://img.test/dish.jpg")

    service = _service(tmp_path, search)
    assert asyncio.run(service.fetch_and_cache("Unknown Diner", "Cubano")) is not None
    assert queries == ["Unknown Diner Cubano food", "Cubano food"]


def test_small_thumbnails_are_skipped(tmp_path):
    def search(query, max_results):
        return [ImageCandidate("https://img.test/icon.jpg", "fake", width=64),
                ImageCandidate("https://img.test/photo.jpg", "fake", width=800)]

    downloaded = []

    def download(url):
        downloaded.append(url)
        return JPEG

    service = _service(tmp_path, search, download)
    assert asyncio.run(service.fetch_and_cache("Icons", "Tacos")) is not None
    # The 64px icon is skipped without downloading it at all.
    assert downloaded == ["https://img.test/photo.jpg"]


def test_menu_codes_and_combo_words_are_dropped_for_search():
    assert core_dish_name("C1 Galbi Combo") == "Galbi"
    assert core_dish_name("石锅拌饭套餐") == "石锅拌饭"
    assert core_dish_name("#3 Fried Chicken Plate") == "Fried Chicken"
    assert core_dish_name("Cubano") == "Cubano"
    assert build_queries("", "C1 Galbi Combo")[-1] == "Galbi food"


def test_second_provider_is_used_when_the_first_finds_nothing(tmp_path):
    used = []

    def empty(query, max_results):
        used.append(("first", query))
        return []

    def backup(query, max_results):
        used.append(("second", query))
        return [ImageCandidate("https://img.test/commons.jpg", "wikimedia", 800, "Photographer · CC BY 2.0")]

    service = _service(tmp_path, empty, providers=[("first", empty, 1), ("second", backup, 1)])
    assert asyncio.run(service.fetch_and_cache("Kroft", "Poutine")) is not None
    assert [name for name, _ in used] == ["first", "second"]
    entry = cache_service.get_image("Kroft", "Poutine")
    assert entry.source == "wikimedia" and "CC BY 2.0" in entry.attribution


def test_wikimedia_results_are_parsed_with_attribution(monkeypatch):
    from app.services import image_sources

    class FakeResponse:
        @staticmethod
        def raise_for_status():
            pass

        @staticmethod
        def json():
            return {"query": {"pages": {"1": {"title": "File:Poutine.jpg", "imageinfo": [{
                "thumburl": "https://upload.wikimedia.org/poutine_800.jpg", "thumbwidth": 800,
                "extmetadata": {"Artist": {"value": "<a href='#'>Jane Doe</a>"},
                                "LicenseShortName": {"value": "CC BY-SA 4.0"}}}]},
                "2": {"title": "File:NoInfo.jpg"}}}}

    monkeypatch.setattr(image_sources.requests, "get", lambda *a, **kw: FakeResponse())
    results = image_sources.search_wikimedia("poutine food", 3)
    assert len(results) == 1
    assert results[0].url.endswith("poutine_800.jpg") and results[0].source == "wikimedia"
    assert results[0].attribution == "Jane Doe · CC BY-SA 4.0 · Wikimedia Commons"
