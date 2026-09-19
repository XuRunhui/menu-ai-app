"""Tests for letting DeepSeek pick the dish photo: batching, bad replies, and the fallbacks."""

import asyncio
import io
import json
from types import SimpleNamespace

import pytest
from PIL import Image

from app.core.config import settings
from app.db.models import ImageSearchFailure
from app.db.session import SessionLocal
from app.services import cache_service, image_judge
from app.services.dish_image_service import DishImageService
from app.services.image_judge import Shortlisted, pick_best, thumbnail
from app.services.image_sources import ImageCandidate


def _photo(width=1200, height=900, color=(200, 80, 60)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="JPEG")
    return buffer.getvalue()


def _shortlist(count: int) -> list[Shortlisted]:
    return [
        Shortlisted(
            candidate=ImageCandidate(f"https://img.test/{i}.jpg", "fake", width=800),
            query="Poutine food", content=b"full-%d" % i, thumbnail=b"thumb-%d" % i,
        )
        for i in range(count)
    ]


class FakeLLM:
    """Records each batch it is shown and answers from a scripted list of choices."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.batches: list[int] = []

    def generate(self, prompt, images=None, **kwargs):
        self.batches.append(len(images or []))
        return self.replies.pop(0) if self.replies else json.dumps({"choice": None})


# ─── Choosing ────────────────────────────────────────────────────────────────


def test_one_call_when_every_candidate_fits_in_a_batch():
    llm = FakeLLM(json.dumps({"choice": 3, "reason": "gravy and curds"}))
    chosen = pick_best(llm, "Kroft", "Poutine", _shortlist(5), batch_size=6)
    assert chosen.content == b"full-2"          # "photo 3" is the third, 0-based index 2
    assert llm.batches == [5]


def test_a_small_batch_limit_runs_a_second_round():
    # Pretend the API only accepts 2 images at a time: 5 candidates -> 3 batches, then a run-off.
    llm = FakeLLM(
        json.dumps({"choice": 1}),      # batch [0,1] -> candidate 0
        json.dumps({"choice": 2}),      # batch [2,3] -> candidate 3
        json.dumps({"choice": None}),   # batch [4]   -> nothing
        json.dumps({"choice": 2}),      # run-off [0,3] -> candidate 3
    )
    chosen = pick_best(llm, "", "Poutine", _shortlist(5), batch_size=2)
    assert chosen.content == b"full-3"
    assert llm.batches == [2, 2, 1, 2]


def test_none_of_these_returns_nothing():
    # A blank card beats a picture of the wrong dish, which is the bug this module fixes.
    llm = FakeLLM(json.dumps({"choice": None, "reason": "all storefronts"}))
    assert pick_best(llm, "", "Poutine", _shortlist(4)) is None


def test_a_single_candidate_is_still_checked():
    llm = FakeLLM(json.dumps({"choice": None}))
    assert pick_best(llm, "", "Poutine", _shortlist(1)) is None
    assert llm.batches == [1]


def test_batch_size_of_one_cannot_loop_forever():
    llm = FakeLLM(*[json.dumps({"choice": 1})] * 12)   # every single-image batch says yes
    assert pick_best(llm, "", "Poutine", _shortlist(3), batch_size=1).content == b"full-0"


# ─── Unreliable replies ──────────────────────────────────────────────────────


@pytest.mark.parametrize("reply", [
    '{"choice": 99}',                       # out of range
    '{"choice": "none"}',                   # refusal as a word
    '{"choice": true}',                     # bool is not an index
    'Sorry, I cannot help with that.',      # not JSON at all
    '',                                     # empty completion
    # A photo named while its own reason rules it out (seen live: a diagram cached as noodles).
    '{"choice": 1, "reason": "It is a chemistry diagram, not food."}',
    '{"choice": 2, "reason": "None of these show poutine"}',
])
def test_unusable_replies_mean_no_match(reply):
    assert pick_best(FakeLLM(reply), "", "Poutine", _shortlist(3)) is None


@pytest.mark.parametrize("reply, expected", [
    ('{"choice": "2"}', b"full-1"),                              # number as a string
    ('```json\n{"choice": 1, "reason": "ok"}\n```', b"full-0"),  # fenced JSON
    ('{"choice": 2, "reason": "looks right"}', b"full-1"),
    ('{"choice": 2, "reason": "Glass of cola, not packaged bottle"}', b"full-1"),  # "not" alone is fine
])
def test_forgiving_parsing(reply, expected):
    assert pick_best(FakeLLM(reply), "", "Poutine", _shortlist(3)).content == expected


# ─── Thumbnails ──────────────────────────────────────────────────────────────


def test_thumbnails_shrink_the_upload():
    original = _photo(1600, 1200)
    small = thumbnail(original, max_px=448)
    with Image.open(io.BytesIO(small)) as image:
        assert max(image.size) == 448
    assert len(small) < len(original) / 2


def test_undecodable_bytes_are_sent_as_they_are():
    assert thumbnail(b"not an image at all") == b"not an image at all"


# ─── Wiring into the image service ───────────────────────────────────────────


def _judging_service(tmp_path, monkeypatch, llm, candidates, download=None):
    monkeypatch.setattr(settings, "dish_image_judge_enabled", True)
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    monkeypatch.setattr(settings, "dish_image_candidates", 4)
    service = DishImageService(images_dir=tmp_path,
                               providers=[("fake", lambda q, n: candidates, 1)])
    service._download_bytes = download or (lambda url: _photo())
    monkeypatch.setattr(service, "_judge_client", lambda: llm)
    return service


def test_the_chosen_photo_is_the_one_cached(tmp_path, monkeypatch):
    candidates = [ImageCandidate(f"https://img.test/{i}.jpg", "duckduckgo", 800) for i in range(4)]
    llm = FakeLLM(json.dumps({"choice": 3}))
    service = _judging_service(tmp_path, monkeypatch, llm, candidates,
                               download=lambda url: _photo(color=(0, 0, int(url[17]) * 60)))

    filename = asyncio.run(service.fetch_and_cache("Kroft", "Poutine"))
    assert filename is not None
    entry = cache_service.get_image("Kroft", "Poutine")
    assert entry.source_url == "https://img.test/2.jpg"
    # The full-size bytes are stored, not the thumbnail sent to the model.
    with Image.open(tmp_path / filename) as image:
        assert image.size == (1200, 900)


def test_rejecting_everything_leaves_no_image(tmp_path, monkeypatch):
    candidates = [ImageCandidate(f"https://img.test/{i}.jpg", "duckduckgo", 800) for i in range(3)]
    service = _judging_service(tmp_path, monkeypatch, FakeLLM(json.dumps({"choice": None})), candidates)

    assert asyncio.run(service.fetch_and_cache("Kroft", "Weird Special")) is None
    assert cache_service.recent_image_failure("Kroft", "Weird Special")
    # The judge saw photos and turned them all down: that answer is kept for days, not minutes.
    with SessionLocal() as db:
        row = db.get(ImageSearchFailure, cache_service.image_key("Kroft", "Weird Special"))
        assert row.reason == cache_service.NO_MATCHING_PHOTO


def test_a_search_that_finds_nothing_is_remembered_only_briefly(tmp_path, monkeypatch):
    service = _judging_service(tmp_path, monkeypatch, FakeLLM(json.dumps({"choice": None})), [])

    assert asyncio.run(service.fetch_and_cache("Kroft", "Unfindable")) is None
    with SessionLocal() as db:
        row = db.get(ImageSearchFailure, cache_service.image_key("Kroft", "Unfindable"))
        assert row.reason != cache_service.NO_MATCHING_PHOTO


def test_a_failing_judge_still_returns_a_photo(tmp_path, monkeypatch):
    class BrokenLLM:
        def generate(self, *args, **kwargs):
            raise RuntimeError("402 insufficient balance")

    candidates = [ImageCandidate("https://img.test/first.jpg", "duckduckgo", 800)]
    service = _judging_service(tmp_path, monkeypatch, BrokenLLM(), candidates)

    # Out of quota is not a reason to show an empty card; fall back to the old behaviour.
    assert asyncio.run(service.fetch_and_cache("Quota", "Poutine")) is not None
    assert cache_service.get_image("Quota", "Poutine").source_url == "https://img.test/first.jpg"


def test_only_as_many_photos_as_will_be_judged_are_downloaded(tmp_path, monkeypatch):
    downloaded = []
    candidates = [ImageCandidate(f"https://img.test/{i}.jpg", "duckduckgo", 800) for i in range(9)]

    def download(url):
        downloaded.append(url)
        return _photo()

    service = _judging_service(tmp_path, monkeypatch, FakeLLM(json.dumps({"choice": 1})),
                               candidates, download=download)
    asyncio.run(service.fetch_and_cache("Budget", "Poutine"))
    assert len(downloaded) == 4          # settings.dish_image_candidates, not all nine results


def test_prompt_numbers_the_photos_it_sends():
    prompt = image_judge._prompt("Poutine", "Kroft", 3)
    assert "photo 1" in prompt and "photo 3" in prompt
    assert '"choice"' in prompt and "null" in prompt
    assert "Kroft" in prompt and "Poutine" in prompt


# ─── Asking DeepSeek what to search for ──────────────────────────────────────

from app.services.image_judge import suggest_search_terms  # noqa: E402
from app.services.image_sources import commons_queries  # noqa: E402


class TermsAndJudgeLLM:
    """Answers the search-terms prompt (no images) and the judging prompt (images) separately."""

    def __init__(self, terms, judge_choices):
        self.terms, self.judge_choices = terms, list(judge_choices)
        self.term_calls, self.judge_prompts = 0, []

    def generate(self, prompt, images=None, **kwargs):
        if not images:
            self.term_calls += 1
            return json.dumps({"terms": self.terms})
        self.judge_prompts.append(prompt)
        choice = self.judge_choices.pop(0) if self.judge_choices else None
        return json.dumps({"choice": choice})


def _service_with(tmp_path, monkeypatch, llm, results_by_query, used=()):
    """Wikimedia-style provider whose results depend on the exact query."""
    monkeypatch.setattr(settings, "dish_image_judge_enabled", True)
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    monkeypatch.setattr(settings, "dish_image_candidates", 2)
    searched = []

    def search(query, limit):
        searched.append(query)
        return [ImageCandidate(url, "wikimedia", 800) for url in results_by_query.get(query, [])]

    service = DishImageService(images_dir=tmp_path, providers=[
        ("wikimedia", search, 3, lambda restaurant, dish, translated: commons_queries(dish, restaurant, translated))])
    service._download_bytes = lambda url: _photo()
    monkeypatch.setattr(service, "_judge_client", lambda: llm)
    return service, searched


def test_commons_queries_drop_what_commons_cannot_match():
    assert commons_queries("#2 Zingerman's Reuben", "Zingerman's Delicatessen") == ["Reuben"]
    assert commons_queries("Korean Fried Chicken Wings", "Tomukun Korean BBQ") == [
        "Korean Fried Chicken Wings", "Chicken Wings"]            # cuisine words stay
    assert commons_queries("Tomukun Special Ramen", "Tomukun Korean BBQ") == ["Ramen"]
    assert commons_queries("凉皮", "Xi'an Famous Foods", 'Liang Pi "Cold-Skin Noodles"') == [
        "Liang Pi Cold-Skin Noodles", "Cold-Skin Noodles", "凉皮"]  # native script too


def test_search_terms_are_cleaned():
    llm = TermsAndJudgeLLM(["Reuben sandwich", "Reuben sandwich", "", "a b c d e f g", 42, "corned beef"], [])
    assert suggest_search_terms(llm, "#2 Zingerman's Reuben") == ["Reuben sandwich", "corned beef"]


@pytest.mark.parametrize("reply", ["not json", '{"terms": "pastrami"}', '["pastrami"]'])
def test_unusable_search_terms_mean_no_retry(reply):
    llm = SimpleNamespace(generate=lambda *a, **kw: reply)
    assert suggest_search_terms(llm, "Mystery Plate") == []


def test_the_menu_description_reaches_the_terms_prompt():
    prompts = []
    llm = SimpleNamespace(generate=lambda prompt, **kw: prompts.append(prompt) or '{"terms": []}')
    suggest_search_terms(llm, "Ba-corn", "Tomukun", "", "Sweet corn, bacon, mozzarella")
    assert "Sweet corn, bacon, mozzarella" in prompts[0] and "Ba-corn" in prompts[0]


def test_nothing_found_by_name_is_retried_with_suggested_terms(tmp_path, monkeypatch):
    llm = TermsAndJudgeLLM(["pastrami sandwich"], judge_choices=[1])
    service, searched = _service_with(tmp_path, monkeypatch, llm,
                                      {"pastrami sandwich": ["https://img.test/pastrami.jpg"]})

    assert asyncio.run(service.fetch_and_cache("Zingerman's Delicatessen", "#81.5 Rick's 50/50 mix")) is not None
    assert searched[-1] == "pastrami sandwich" and llm.term_calls == 1
    assert cache_service.get_image("Zingerman's Delicatessen", "#81.5 Rick's 50/50 mix").source_url.endswith("pastrami.jpg")


def test_photos_the_judge_rejects_also_trigger_the_retry(tmp_path, monkeypatch):
    # "Reuben" on Commons finds people named Reuben; the judge says none is the dish.
    llm = TermsAndJudgeLLM(["Reuben sandwich"], judge_choices=[None, 1])
    service, searched = _service_with(tmp_path, monkeypatch, llm, {
        "Reuben": ["https://img.test/reuben-the-person.jpg"],
        "Reuben sandwich": ["https://img.test/reuben-sandwich.jpg"]})

    assert asyncio.run(service.fetch_and_cache("Zingerman's Delicatessen", "#2 Zingerman's Reuben")) is not None
    assert searched == ["Reuben", "Reuben sandwich"]
    assert cache_service.get_image("Zingerman's Delicatessen", "#2 Zingerman's Reuben").source_url.endswith("reuben-sandwich.jpg")


def test_no_terms_are_requested_when_the_name_works(tmp_path, monkeypatch):
    llm = TermsAndJudgeLLM(["unused"], judge_choices=[1])
    service, _ = _service_with(tmp_path, monkeypatch, llm, {"Japchae": ["https://img.test/japchae.jpg"]})
    assert asyncio.run(service.fetch_and_cache("Tomukun Korean BBQ", "Japchae")) is not None
    assert llm.term_calls == 0


def test_without_deepseek_there_is_no_retry(tmp_path, monkeypatch):
    service, searched = _service_with(tmp_path, monkeypatch, None, {})
    monkeypatch.setattr(service, "_judge_client", lambda: None)
    assert asyncio.run(service.fetch_and_cache("Kroft", "Mystery Stew")) is None
    assert searched == ["Mystery Stew"]


def test_a_photo_is_not_reused_for_another_dish_at_the_same_restaurant(tmp_path, monkeypatch):
    llm = TermsAndJudgeLLM(["Reuben sandwich"], judge_choices=[1, 1, 1, 1])
    results = {"Reuben sandwich": ["https://img.test/reuben-a.jpg", "https://img.test/reuben-b.jpg"]}
    service, _ = _service_with(tmp_path, monkeypatch, llm, results)

    asyncio.run(service.fetch_and_cache("Deli", "#2 Deli's Reuben"))
    asyncio.run(service.fetch_and_cache("Deli", "#48 Deli's Brooklyn Reuben"))
    first = cache_service.get_image("Deli", "#2 Deli's Reuben").source_url
    second = cache_service.get_image("Deli", "#48 Deli's Brooklyn Reuben").source_url
    assert first != second

    # Another restaurant may still use the same photo.
    asyncio.run(service.fetch_and_cache("Other Deli", "Reuben Special"))
    assert cache_service.get_image("Other Deli", "Reuben Special") is not None


def test_the_judge_sees_the_menu_description(tmp_path, monkeypatch):
    llm = TermsAndJudgeLLM([], judge_choices=[1])
    service, _ = _service_with(tmp_path, monkeypatch, llm, {"Ba-corn": ["https://img.test/corn.jpg"]})
    asyncio.run(service.fetch_and_cache("Tomukun Korean BBQ", "Ba-corn", "",
                                        "Sweet corn, bacon, mozzarella"))
    assert "Sweet corn, bacon, mozzarella" in llm.judge_prompts[0]


def test_dishes_searched_at_the_same_moment_do_not_share_a_photo(tmp_path, monkeypatch):
    # Both dishes start before either has picked, and the judge would pick the same first photo
    # for both. The second to claim it has to choose again.
    llm = TermsAndJudgeLLM([], judge_choices=[1, 1, 1, 1])
    results = {"Reuben": ["https://img.test/reuben-a.jpg", "https://img.test/reuben-b.jpg"]}
    service, _ = _service_with(tmp_path, monkeypatch, llm, results)

    async def both():
        return await asyncio.gather(service.fetch_and_cache("Race Deli", "#2 Race's Reuben"),
                                    service.fetch_and_cache("Race Deli", "#18 Race's Reuben"))

    asyncio.run(both())
    urls = {cache_service.get_image("Race Deli", dish).source_url
            for dish in ("#2 Race's Reuben", "#18 Race's Reuben")}
    assert urls == {"https://img.test/reuben-a.jpg", "https://img.test/reuben-b.jpg"}
