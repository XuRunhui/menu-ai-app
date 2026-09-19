"""Tests for the dining assistant: the scripted flow, the tool loop, and the fallbacks."""

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.models.assistant import AssistantRequest, ChatMessage, DinerContext
from app.services.assistant import agent, tools

client = TestClient(app)

PLACES = [
    {"place_id": "near", "name": "Corner Tofu", "formatted_address": "1 Main St",
     "rating": 4.6, "user_ratings_total": 900, "price_level": 2,
     "geometry": {"location": {"lat": 42.281, "lng": -83.748}},
     "opening_hours": {"open_now": True}},
    {"place_id": "far", "name": "Distant Diner", "formatted_address": "99 Far Rd",
     "rating": 4.9, "geometry": {"location": {"lat": 42.500, "lng": -83.748}}},
    {"place_id": "closed", "name": "Gone Forever", "business_status": "CLOSED_PERMANENTLY",
     "geometry": {"location": {"lat": 42.282, "lng": -83.749}}},
]

ANN_ARBOR = DinerContext(latitude=42.280, longitude=-83.748)


def _chat(*user_texts: str, context: DinerContext = DinerContext()) -> AssistantRequest:
    return AssistantRequest(
        messages=[ChatMessage(role="user", content=text) for text in user_texts], context=context)


@pytest.fixture
def places(monkeypatch):
    """Stand in for Google Places and the review-to-dishes step; records the searches made."""
    searches = []

    class FakeService:
        def __init__(self, api_key):
            pass

        def search_places(self, query, location=None, radius=50000, use_exact_match=True):
            searches.append({"query": query, "location": location, "radius": radius})
            return {"results": list(PLACES), "status": "OK"}

        def get_full_place_data(self, place_id):
            return {"place": {**PLACES[0], "website": "https://corner.example",
                              "opening_hours": {"open_now": True, "weekday_text": ["Monday: 11–9"]}},
                    "reviews": [{"text": "The soon tofu is unreal."}]}

    monkeypatch.setattr(settings, "google_places_api_key", "test-key")
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    monkeypatch.setattr("app.services.google_places_service.GooglePlacesService", FakeService)
    # Reading dishes out of reviews is itself an LLM call; stub it so no test reaches the network.
    monkeypatch.setattr("app.services.dish_extractor.extract_popular_dishes",
                        lambda reviews, api_key, top_n=10: [
                            {"name": "Soon Tofu", "mention_count": 7}])
    return searches


# ─── Reading the conversation ────────────────────────────────────────────────


def test_the_three_questions_are_asked_in_order():
    profile = agent.read_profile(_chat("something spicy").messages, DinerContext())
    assert profile.craving == "something spicy" and not profile.near

    profile = agent.read_profile(_chat("something spicy", "Ann Arbor").messages, DinerContext())
    assert profile.near == "Ann Arbor" and profile.radius_km is None

    profile = agent.read_profile(
        _chat("something spicy", "Ann Arbor", "10 minute walk").messages, DinerContext())
    assert profile.ready and profile.radius_km == 0.8


def test_shared_coordinates_skip_the_location_question():
    # The second message answers "how far", because the browser already answered "where".
    profile = agent.read_profile(_chat("ramen", "20 minute drive").messages, ANN_ARBOR)
    assert profile.near == "your current location" and profile.radius_km == 12.0


@pytest.mark.parametrize("text, km", [
    ("10 minute walk", 0.8), ("20 min drive", 12.0), ("30 minutes by bus", 10.5),
    ("2 miles", 3.2), ("5km", 5.0), ("walking distance", 1.5),
    ("I don't mind how far", 25.0), ("happy to drive", 10.0),
])
def test_distances_in_plain_english(text, km):
    assert tools.parse_distance(text) == km


def test_an_unparseable_distance_still_moves_on():
    # Re-asking a question the visitor already answered is worse than assuming a default.
    profile = agent.read_profile(_chat("sushi", "Chicago", "uhh, purple?").messages, DinerContext())
    assert profile.ready and profile.radius_km == tools.DEFAULT_RADIUS_KM


# ─── Scripted flow ───────────────────────────────────────────────────────────


def test_scripted_flow_asks_then_searches(places, monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "")

    first = agent.respond(_chat("something spicy"))
    assert "Where are you" in first.reply and first.needs_location
    assert first.quick_replies == ["Use my location"]
    assert first.llm_available is False

    second = agent.respond(_chat("something spicy", "Ann Arbor"))
    assert "how far" in second.reply.lower()

    third = agent.respond(_chat("something spicy", "Ann Arbor", "10 minute drive"))
    assert "Corner Tofu" in third.reply
    assert [card.place_id for card in third.restaurants] == ["near", "far"]
    assert places[-1]["query"] == "something spicy Ann Arbor"


def test_the_opening_turn_introduces_itself(monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    opening = agent.respond(AssistantRequest(messages=[ChatMessage(role="user", content="hi")]))
    # "hi" is taken as the craving, so it moves on rather than looping on the greeting.
    assert opening.reply == agent.ASK_LOCATION


# ─── Distance handling ───────────────────────────────────────────────────────


def test_results_are_filtered_to_what_is_actually_within_reach(places):
    payload, cards = tools.find_restaurants("tofu", radius_km=5, context=ANN_ARBOR)
    assert [card.name for card in cards] == ["Corner Tofu"]      # the 24 km one is dropped
    assert cards[0].distance_km == pytest.approx(0.1, abs=0.2)
    assert payload["radius_km"] == 5


def test_nothing_in_range_offers_the_nearest_and_says_so(places):
    payload, cards = tools.find_restaurants("tofu", radius_km=0.01, context=ANN_ARBOR)
    assert [card.name for card in cards] == ["Corner Tofu", "Distant Diner"]
    assert "nearest" in payload["note"].lower()


def test_permanently_closed_places_are_dropped(places):
    _, cards = tools.find_restaurants("tofu", radius_km=50, context=ANN_ARBOR)
    assert "Gone Forever" not in [card.name for card in cards]


def test_coordinates_bias_the_search_instead_of_the_query(places):
    tools.find_restaurants("ramen", radius_km=3, context=ANN_ARBOR)
    assert places[-1] == {"query": "ramen", "location": "42.28,-83.748", "radius": 3000}


def test_a_refusal_from_google_is_reported_not_swallowed(monkeypatch):
    monkeypatch.setattr(settings, "google_places_api_key", "test-key")

    class Denied:
        def __init__(self, api_key):
            pass

        def search_places(self, *args, **kwargs):
            return {"results": [], "status": "REQUEST_DENIED", "error_message": "API not enabled"}

    monkeypatch.setattr("app.services.google_places_service.GooglePlacesService", Denied)
    payload, cards = tools.find_restaurants("ramen", near="Ann Arbor")
    assert "REQUEST_DENIED" in payload["error"] and "API not enabled" in payload["error"]
    assert cards == []


# ─── Tool loop ───────────────────────────────────────────────────────────────


def _tool_call(call_id, name, **arguments):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(
        name=name, arguments=json.dumps(arguments)))


class FakeLLM:
    """Replays scripted assistant messages and records what it was sent."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.seen: list[list[dict]] = []
        self.tool_choices: list = []

    def chat(self, messages, tools=None, tool_choice=None, max_tokens=None):
        self.seen.append([dict(m) for m in messages])
        self.tool_choices.append(tool_choice)
        return self.replies.pop(0) if self.replies else SimpleNamespace(content="…", tool_calls=None)


def test_the_model_can_search_and_then_answer(places):
    llm = FakeLLM(
        SimpleNamespace(content="", tool_calls=[
            _tool_call("c1", "find_restaurants", what="tofu stew", radius_km=3)]),
        SimpleNamespace(content="Corner Tofu is 100 m away and open now.", tool_calls=None),
    )
    response = agent.run_with_model(_chat("korean tofu, nearby", context=ANN_ARBOR), llm)

    assert response.reply.startswith("Corner Tofu")
    assert response.tools_used == ["find_restaurants"]
    assert [card.place_id for card in response.restaurants] == ["near"]

    # The tool result went back to the model as a role:tool message tied to the call id.
    tool_message = llm.seen[1][-1]
    assert tool_message["role"] == "tool" and tool_message["tool_call_id"] == "c1"
    assert "Corner Tofu" in tool_message["content"]


def test_the_transcript_round_trips_tool_calls(places):
    llm = FakeLLM(
        SimpleNamespace(content="", tool_calls=[_tool_call("c1", "find_restaurants", what="tofu")]),
        SimpleNamespace(content="Try Corner Tofu.", tool_calls=None),
    )
    first = agent.run_with_model(_chat("tofu", context=ANN_ARBOR), llm)

    # Sending the transcript straight back must produce a conversation the API will accept.
    follow_up = AssistantRequest(
        messages=first.messages + [ChatMessage(role="user", content="what should I order?")],
        context=ANN_ARBOR)
    second = FakeLLM(SimpleNamespace(content="The soon tofu.", tool_calls=None))
    agent.run_with_model(follow_up, second)

    roles = [m["role"] for m in second.seen[0]]
    assert roles == ["system", "user", "assistant", "tool", "assistant", "user"]
    assert second.seen[0][2]["tool_calls"][0]["id"] == "c1"


def test_chips_stay_quiet_while_the_model_asks_its_own_questions(places):
    llm = FakeLLM(SimpleNamespace(content="Korean, Thai, or Mexican?", tool_calls=None))
    response = agent.run_with_model(_chat("something spicy", context=ANN_ARBOR), llm)
    # Guessed chips wouldn't answer a question we didn't write, so none are offered.
    assert response.quick_replies == []


def test_chips_offer_location_and_follow_ups_when_they_fit():
    assert agent.model_quick_replies(DinerContext(), False) == ["Use my location"]
    assert agent.model_quick_replies(ANN_ARBOR, True) == agent.FOUND_CHIPS
    assert agent.model_quick_replies(DinerContext(location_text="Ann Arbor"), False) == []


def test_the_tool_budget_is_capped(places):
    # A model that only ever wants to search must still be made to answer.
    searching = SimpleNamespace(content="", tool_calls=[_tool_call("c", "find_restaurants", what="x")])
    llm = FakeLLM(*[searching] * agent.MAX_TOOL_ROUNDS,
                  SimpleNamespace(content="Here are some options.", tool_calls=None))
    response = agent.run_with_model(_chat("food", context=ANN_ARBOR), llm)

    assert len(response.tools_used) == agent.MAX_TOOL_ROUNDS
    assert llm.tool_choices == ["auto"] * agent.MAX_TOOL_ROUNDS + ["none"]
    assert response.reply == "Here are some options."


def test_a_broken_tool_call_does_not_end_the_conversation(places):
    broken = SimpleNamespace(id="c1", function=SimpleNamespace(
        name="find_restaurants", arguments="{not json"))
    llm = FakeLLM(
        SimpleNamespace(content="", tool_calls=[broken]),
        SimpleNamespace(content="What are you in the mood for?", tool_calls=None),
    )
    response = agent.run_with_model(_chat("hi", context=ANN_ARBOR), llm)
    assert response.reply == "What are you in the mood for?"
    assert "error" in llm.seen[1][-1]["content"]


def test_looking_up_one_place_keeps_the_other_results_on_screen(places):
    llm = FakeLLM(
        SimpleNamespace(content="", tool_calls=[
            _tool_call("c1", "find_restaurants", what="tofu", radius_km=50)]),
        SimpleNamespace(content="", tool_calls=[
            _tool_call("c2", "restaurant_highlights", place_id="near")]),
        SimpleNamespace(content="Get the soon tofu at Corner Tofu.", tool_calls=None),
    )
    response = agent.run_with_model(_chat("tofu", context=ANN_ARBOR), llm)

    assert response.tools_used == ["find_restaurants", "restaurant_highlights"]
    # The reply suggests alternatives, so the alternatives have to stay tappable.
    assert [card.place_id for card in response.restaurants] == ["near", "far"]
    # The dishes reviewers name reach the model, which is the point of the second call.
    assert "Soon Tofu" in llm.seen[2][-1]["content"]


def test_follow_up_chips_survive_a_turn_that_only_looks_one_place_up(places):
    llm = FakeLLM(
        SimpleNamespace(content="", tool_calls=[_tool_call("c1", "find_restaurants", what="tofu")]),
        SimpleNamespace(content="Corner Tofu is closest.", tool_calls=None),
    )
    first = agent.run_with_model(_chat("tofu", context=ANN_ARBOR), llm)
    assert first.quick_replies == agent.FOUND_CHIPS

    # Next turn returns no new cards, but the old ones are still on screen.
    detail = FakeLLM(
        SimpleNamespace(content="", tool_calls=[
            _tool_call("c2", "restaurant_highlights", place_id="near")]),
        SimpleNamespace(content="Reviewers order the soon tofu.", tool_calls=None),
    )
    second = agent.run_with_model(AssistantRequest(
        messages=first.messages + [ChatMessage(role="user", content="what do I order?")],
        context=ANN_ARBOR), detail)

    assert second.restaurants == []
    assert second.quick_replies == agent.FOUND_CHIPS


def test_an_oversized_tool_result_is_cut_not_crashed(monkeypatch):
    monkeypatch.setattr(agent, "execute", lambda *a, **kw: ({"passages": ["x" * 40_000]}, []))
    llm = FakeLLM(
        SimpleNamespace(content="", tool_calls=[_tool_call("c1", "food_knowledge", question="?")]),
        SimpleNamespace(content="Here you go.", tool_calls=None),
    )
    # The transcript goes back through the browser, where ChatMessage caps content at 8000 chars.
    response = agent.run_with_model(_chat("tell me about bibimbap"), llm)
    assert response.reply == "Here you go."
    assert all(len(m.content) <= agent.MAX_TOOL_RESULT_CHARS for m in response.messages)


def test_an_unknown_tool_is_answered_not_raised():
    payload, cards = tools.execute("delete_everything", {}, DinerContext())
    assert "Unknown tool" in payload["error"] and cards == []


def test_a_dead_model_falls_back_to_the_script(places, monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")

    class Broken:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("402 insufficient balance")

    monkeypatch.setattr("app.services.llm_client.LLMClient", Broken)
    response = agent.respond(_chat("tofu", "Ann Arbor", "10 minute drive"))

    # Out of credit is exactly when a recruiter is looking; it still finds them dinner.
    assert "Corner Tofu" in response.reply and response.llm_available is False


def test_long_conversations_are_trimmed_to_a_valid_window():
    messages = [ChatMessage(role="user", content=f"turn {i}") for i in range(40)]
    messages.insert(0, ChatMessage(role="tool", tool_call_id="orphan", content="{}"))
    window = agent._tail(messages, agent.MAX_HISTORY_MESSAGES)

    assert len(window) <= agent.MAX_HISTORY_MESSAGES
    assert window[0].role == "user"          # never opens on an orphaned tool result


def test_the_browser_keeps_more_history_than_the_model_is_shown(places):
    history = []
    for i in range(20):
        history += [ChatMessage(role="user", content=f"q{i}"),
                    ChatMessage(role="assistant", content=f"a{i}")]

    llm = FakeLLM(SimpleNamespace(content="Latest answer.", tool_calls=None))
    response = agent.run_with_model(
        AssistantRequest(messages=history[-59:], context=ANN_ARBOR), llm)

    # The model sees a window; the browser keeps its scrollback, capped at what it may send back.
    assert len(llm.seen[0]) <= agent.MAX_HISTORY_MESSAGES + 1        # + the system prompt
    assert len(response.messages) <= agent.MAX_TRANSCRIPT_MESSAGES
    assert len(response.messages) > agent.MAX_HISTORY_MESSAGES
    assert response.messages[-1].content == "Latest answer."


# ─── Menus ───────────────────────────────────────────────────────────────────


def test_review_dishes_are_never_passed_off_as_the_menu(places):
    payload, _ = tools.restaurant_highlights("near")
    assert payload["menu_online"] is False
    assert payload["popular_dishes"] == [{"name": "Soon Tofu", "mentions": 7}]
    # The model has to be told what these are, or it presents review chatter as the menu — and
    # pointed at the tool that can actually check, or it declares the menu missing without looking.
    assert "not the restaurant's menu" in payload["note"]
    assert "read_menu" in payload["note"]


def test_a_place_with_no_review_dishes_is_sent_to_look_at_the_photos(places, monkeypatch):
    monkeypatch.setattr("app.services.dish_extractor.extract_popular_dishes",
                        lambda reviews, api_key, top_n=10: [])
    payload, _ = tools.restaurant_highlights("near")
    assert payload["popular_dishes"] == []
    assert "Do not guess" in payload["note"]
    assert "read_menu" in payload["note"]


def test_details_alone_never_claims_a_menu_is_missing(places):
    llm = FakeLLM(
        SimpleNamespace(content="", tool_calls=[
            _tool_call("c1", "restaurant_highlights", place_id="near")]),
        SimpleNamespace(content="Reviewers order the soon tofu.", tool_calls=None),
    )
    response = agent.run_with_model(_chat("what's on the menu at corner tofu?"), llm)
    # The photos haven't been checked yet, so offering the upload here would jump the gun.
    assert response.menu_upload is None


def test_searching_alone_does_not_offer_an_upload(places):
    llm = FakeLLM(
        SimpleNamespace(content="", tool_calls=[_tool_call("c1", "find_restaurants", what="tofu")]),
        SimpleNamespace(content="Corner Tofu is closest.", tool_calls=None),
    )
    assert agent.run_with_model(_chat("tofu", context=ANN_ARBOR), llm).menu_upload is None


# ─── read_menu: every source, labelled ───────────────────────────────────────


def _gathered(website_menu=None, website_status="found"):
    from app.models.menu import MenuCategory, MenuItem, ParsedMenu
    from app.models.menu_sources import SourceReport, SourceResult, SourcedMenu
    from app.services.menu_sources.gather import Gathered
    from app.services.menu_sources.merge import combine

    def menu(*names):
        return ParsedMenu(detected_language="English", menu=[
            MenuCategory(category="Menu", items=[MenuItem(name=n, price=10.0) for n in names])])

    website_menu = menu(*website_menu) if website_menu else None
    results = [
        SourceResult(report=SourceReport(kind="website", status=website_status,
                                         detail="Read dishes from cornertofu.com/menu."),
                     menu=website_menu, website_trusted=True),
    ]
    sources = [SourcedMenu(kind=r.report.kind, menu=r.menu) for r in results if r.menu]
    return Gathered("Corner Tofu", results, combine(sources))


def test_read_menu_puts_every_source_on_screen_and_a_summary_in_the_prompt(places, monkeypatch):
    dishes = [f"Stew {i}" for i in range(30)]
    monkeypatch.setattr("app.services.menu_sources.gather.gather",
                        lambda place_id, **kw: _gathered(dishes))
    llm = FakeLLM(
        SimpleNamespace(content="", tool_calls=[_tool_call("c1", "read_menu", place_id="near")]),
        SimpleNamespace(content="From their website: 30 dishes.", tool_calls=None),
    )
    response = agent.run_with_model(_chat("what's on the menu?"), llm)

    found = response.found_menu
    assert found.restaurant_name == "Corner Tofu" and found.combined.total_items == 30
    assert [r.report.kind for r in found.results] == ["website"]
    assert all(i.sources == ["website"] for c in found.combined.menu.menu for i in c.items)

    # The model sees which source said what, and a sample — never the whole menu.
    tool_message = llm.seen[1][-1]["content"]
    assert "the restaurant's website" in tool_message
    assert tools.FULL_MENU_KEY not in tool_message
    assert len(tool_message) < 4000
    assert response.menu_upload is None


def test_nothing_from_any_source_turns_into_the_upload_offer(places, monkeypatch):
    monkeypatch.setattr("app.services.menu_sources.gather.gather",
                        lambda place_id, **kw: _gathered(website_status="unavailable"))
    llm = FakeLLM(
        SimpleNamespace(content="", tool_calls=[_tool_call("c1", "read_menu", place_id="near")]),
        SimpleNamespace(content="Their menu isn't online — can you send a photo?", tool_calls=None),
    )
    response = agent.run_with_model(_chat("what do they serve?"), llm)
    assert response.found_menu is None
    assert response.menu_upload.reason == "no_menu_online" and response.menu_upload.place_id == "near"


def test_a_menu_lookup_outage_is_not_reported_as_a_missing_menu(places, monkeypatch):
    monkeypatch.setattr(settings, "google_places_api_key", "")
    llm = FakeLLM(
        SimpleNamespace(content="", tool_calls=[_tool_call("c1", "read_menu", place_id="near")]),
        SimpleNamespace(content="I can't reach Google right now.", tool_calls=None),
    )
    response = agent.run_with_model(_chat("what do they serve?"), llm)
    assert response.menu_upload is None and response.found_menu is None


# ─── Knowledge tool ──────────────────────────────────────────────────────────


def test_knowledge_lookups_are_trimmed_for_the_prompt(monkeypatch):
    monkeypatch.setattr("app.knowledge.retrieval.search_passages", lambda db, q, top_k=5: [
        {"text": "x" * 2000, "document_title": "Larousse", "license": "PD", "page": 3}])
    payload, _ = tools.food_knowledge("what goes with bibimbap")
    assert len(payload["passages"][0]["text"]) == tools.PASSAGE_CHARS
    assert payload["passages"][0]["source"] == "Larousse"


def test_a_broken_knowledge_base_is_not_fatal(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("no embeddings")

    monkeypatch.setattr("app.knowledge.retrieval.search_passages", boom)
    payload, _ = tools.food_knowledge("anything")
    assert "unavailable" in payload["error"]


# ─── Endpoint ────────────────────────────────────────────────────────────────


def test_endpoint_returns_a_transcript_to_send_back(places, monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    response = client.post("/api/v1/assistant/chat", json={
        "messages": [{"role": "user", "content": "noodles"}],
        "context": {"location_text": "Ann Arbor", "radius_km": 5},
    })
    assert response.status_code == 200
    body = response.json()
    assert body["restaurants"][0]["name"] == "Corner Tofu"
    assert [m["role"] for m in body["messages"]] == ["user", "assistant"]
    assert body["llm_available"] is False


def test_endpoint_rejects_an_empty_conversation():
    assert client.post("/api/v1/assistant/chat", json={"messages": []}).status_code == 422


def test_the_prompt_sends_menu_questions_to_read_menu():
    # An earlier edit to this rule silently failed to apply, leaving an old line that told the
    # model menus can't be fetched at all — contradicting the read_menu tool. Check the real text.
    prompt = agent._system_prompt(DinerContext())
    assert "read_menu" in prompt
    assert "cannot fetch a restaurant's menu" not in prompt
    assert "Google photo" not in prompt
