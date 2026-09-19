"""The tools the assistant can call, and the plain functions behind them.

Each tool is a thin wrapper over something the app already does, so the assistant reaches the same
Google Places search and the same knowledge base the rest of the UI uses, rather than a second,
divergent copy of them.

    find_restaurants        Google Places text search, biased and then filtered by how far the
                            diner is willing to travel.
    restaurant_highlights   Place details plus the dishes reviewers keep naming (costs an LLM call).
    food_knowledge          The local knowledge base — free, offline, no API spend.

Two rules shape the design:

- **Nothing is stored.** Google's terms let us keep a ``place_id`` and nothing else, so results
  are passed straight to the model and dropped. That is also why the assistant's replies are
  never written to the LLM cache.
- **Tools fail into words, not exceptions.** Every executor returns a dict; an outage becomes
  ``{"error": "..."}`` that the model can read and explain, instead of a 500 that ends the chat.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any, Optional

from app.core.config import settings
from app.models.assistant import DinerContext, RestaurantCard

logger = logging.getLogger(__name__)

MAX_RESULTS = 5
DEFAULT_RADIUS_KM = 8.0
# Google's location+radius is a bias, not a filter, so results are checked against the radius here.
# Nothing inside it means we show the nearest few anyway and say so.
NEAREST_FALLBACK = 3
MAX_KNOWLEDGE_PASSAGES = 3

PASSAGE_CHARS = 600

# Where read_menu hands the combined menu to the agent. Stripped before the model sees the
# result: a full menu is dozens of items and belongs on screen, not in the prompt.
FULL_MENU_KEY = "_full_menu"

# Every answer about "the menu" has to be honest about where its dish names came from — and must
# not claim a menu is unavailable before read_menu has actually looked for one.
REVIEWS_NOT_MENU = (
    "These are dishes reviewers mention, not the restaurant's menu. Present them as what people "
    "order. If the diner wants the menu itself, call read_menu — do not tell them the menu "
    "is unavailable until that tool has looked and come back empty."
)
NO_REVIEW_DISHES = (
    "No dish information from reviews for this place. Do not guess at what it serves. If the "
    "diner wants to know, call read_menu to look for its menu."
)
MENU_FOUND = (
    "Say the menu came from the restaurant's website, and that a website can be out of date. "
    "Don't invent dishes that aren't listed. The full menu, labelled by source, is already on "
    "screen next to your reply, and the diner can add a photo of the menu there if it looks "
    "incomplete."
)
NO_MENU_ONLINE = (
    "Tell the diner plainly that this restaurant's menu isn't available online, and offer to read "
    "a photo of the menu if they can take one — Menuist will parse and translate it. Do not guess "
    "at what the menu contains."
)

# Rough travel speeds for turning "20 minutes away" into kilometres.
KM_PER_MINUTE = {"walk": 0.08, "transit": 0.35, "drive": 0.6}


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "find_restaurants",
            "description": (
                "Search for restaurants near the diner. Call this once you know roughly what they "
                "feel like eating and where they are. Returns real places with ratings, price "
                "level and distance."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "what": {
                        "type": "string",
                        "description": (
                            "What to search for: a cuisine, a dish, or a mood translated into "
                            "food terms, e.g. 'korean tofu stew', 'ramen', 'cheap tacos'."
                        ),
                    },
                    "near": {
                        "type": "string",
                        "description": (
                            "Where to search, as the diner described it, e.g. 'Ann Arbor', "
                            "'near campus', '94103'. Leave empty if their coordinates are known."
                        ),
                    },
                    "radius_km": {
                        "type": "number",
                        "description": (
                            "How far they are willing to travel, in kilometres. Convert times "
                            "yourself: a 10 minute walk is about 1 km, a 20 minute drive about 12 km."
                        ),
                    },
                    "open_now": {
                        "type": "boolean",
                        "description": "Only return places that are open right now.",
                    },
                },
                "required": ["what"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "restaurant_highlights",
            "description": (
                "Look up one restaurant's practical details: opening hours, price level, phone, "
                "website, and the dishes its reviewers mention most often. This is review "
                "chatter, NOT the restaurant's menu — for the menu itself use read_menu. "
                "Use a place_id from find_restaurants."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "place_id": {"type": "string", "description": "place_id from find_restaurants."},
                },
                "required": ["place_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_menu",
            "description": (
                "Read a restaurant's actual menu from its own website (menu pages, PDFs and "
                "photos of the menu posted there). This is the ONLY way to answer what is on the menu, "
                "what a place serves, or what things cost — never answer those from reviews, and "
                "never say a menu is unavailable until this tool has returned found=false. Many "
                "restaurants have no menu online, so found=false is normal. Slow and costs real "
                "money: call it at most once per restaurant."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "place_id": {"type": "string", "description": "place_id from find_restaurants."},
                },
                "required": ["place_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "food_knowledge",
            "description": (
                "Search Menuist's food knowledge base (cookbooks, Wikipedia meal customs, "
                "ingredient pairings) for background on a dish, cuisine or pairing. Use it to "
                "explain or justify a suggestion. Free and offline — prefer it over guessing."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "What to look up, e.g. 'what is served with bibimbap'.",
                    },
                },
                "required": ["question"],
            },
        },
    },
]

TOOL_NAMES = [schema["function"]["name"] for schema in TOOL_SCHEMAS]


# ─── Distance helpers ────────────────────────────────────────────────────────


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in kilometres."""
    radius = 6371.0
    d_lat, d_lng = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng / 2) ** 2)
    return radius * 2 * math.asin(math.sqrt(a))


def parse_distance(text: str) -> Optional[float]:
    """Read "15 minute walk", "2 miles", "5km", "walking distance" as kilometres.

    Used by the scripted flow, which has no model to do the conversion for it.
    """
    lowered = text.lower()

    minutes = re.search(r"(\d+)\s*(?:-|\s)?\s*(?:min|minute)s?\b", lowered)
    if minutes:
        mode = "drive" if re.search(r"driv|car", lowered) else \
               "transit" if re.search(r"bus|train|transit|subway|metro", lowered) else "walk"
        return round(int(minutes.group(1)) * KM_PER_MINUTE[mode], 1)

    miles = re.search(r"(\d+(?:\.\d+)?)\s*(?:mi\b|mile)", lowered)
    if miles:
        return round(float(miles.group(1)) * 1.609, 1)

    kilometres = re.search(r"(\d+(?:\.\d+)?)\s*(?:km|kilomet)", lowered)
    if kilometres:
        return float(kilometres.group(1))

    if "walk" in lowered:
        return 1.5
    if re.search(r"anywhere|any distance|far|whatever|don'?t mind|no limit", lowered):
        return 25.0
    if re.search(r"driv|car", lowered):
        return 10.0
    return None


# ─── find_restaurants ────────────────────────────────────────────────────────


def _card(place: dict, context: DinerContext) -> RestaurantCard:
    location = (place.get("geometry") or {}).get("location") or {}
    distance = None
    if context.latitude is not None and context.longitude is not None and location.get("lat") is not None:
        distance = round(haversine_km(context.latitude, context.longitude,
                                      location["lat"], location["lng"]), 1)
    return RestaurantCard(
        place_id=place.get("place_id", ""),
        name=place.get("name", ""),
        address=place.get("formatted_address") or place.get("vicinity") or "",
        rating=place.get("rating"),
        user_ratings_total=place.get("user_ratings_total"),
        price_level=place.get("price_level"),
        open_now=(place.get("opening_hours") or {}).get("open_now"),
        distance_km=distance,
    )


def find_restaurants(what: str, near: str = "", radius_km: Optional[float] = None,
                     open_now: bool = False,
                     context: DinerContext = DinerContext()) -> tuple[dict, list[RestaurantCard]]:
    """Search Google Places, then keep what is actually within reach."""
    if not settings.google_places_api_key:
        return {"error": "Restaurant search is not configured on this deployment."}, []

    from app.services.google_places_service import GooglePlacesService

    radius = radius_km or context.radius_km or DEFAULT_RADIUS_KM
    has_coordinates = context.latitude is not None and context.longitude is not None
    # With coordinates the query stays clean and the location does the work; without them the
    # place name has to carry it, or Google answers from wherever the server happens to be.
    query = what.strip() if has_coordinates and not near else " ".join(
        part for part in [what.strip(), (near or context.location_text).strip()] if part)
    if not query:
        return {"error": "Ask the diner what they feel like eating first."}, []

    try:
        result = GooglePlacesService(settings.google_places_api_key).search_places(
            query,
            location=f"{context.latitude},{context.longitude}" if has_coordinates else None,
            radius=int(radius * 1000),
            use_exact_match=False,
        )
    except Exception as exc:
        logger.warning("assistant: place search failed for %r: %s", query, exc)
        return {"error": f"The restaurant search failed: {exc}"}, []

    if result["status"] not in ("OK", "ZERO_RESULTS"):
        detail = result.get("error_message") or result["status"]
        logger.error("assistant: Google Places returned %s (%s)", result["status"], detail)
        return {"error": f"Google Places is refusing the request ({result['status']}): {detail}"}, []

    places = [p for p in result["results"] if p.get("business_status") != "CLOSED_PERMANENTLY"]
    if open_now:
        places = [p for p in places if (p.get("opening_hours") or {}).get("open_now") is not False]

    cards = [_card(place, context) for place in places if place.get("place_id")]
    beyond_radius = False
    if has_coordinates:
        cards.sort(key=lambda card: card.distance_km if card.distance_km is not None else 999)
        within = [card for card in cards if card.distance_km is None or card.distance_km <= radius]
        if within:
            cards = within
        elif cards:
            # Better to offer the nearest three and be honest than to answer "nothing found".
            cards, beyond_radius = cards[:NEAREST_FALLBACK], True

    cards = cards[:MAX_RESULTS]
    payload = {
        "query": query,
        "radius_km": radius,
        "results": [card.model_dump(exclude_none=True) for card in cards],
    }
    if beyond_radius:
        payload["note"] = (f"Nothing within {radius:g} km. These are the nearest matches — "
                           f"say so and give their distance.")
    elif not cards:
        payload["note"] = "No matches. Suggest widening the area or a different kind of food."
    return payload, cards


# ─── restaurant_highlights ───────────────────────────────────────────────────


def restaurant_highlights(place_id: str) -> tuple[dict, list[RestaurantCard]]:
    """Details plus the dishes reviewers name most often, for one place."""
    if not settings.google_places_api_key:
        return {"error": "Restaurant details are not configured on this deployment."}, []

    from app.services.google_places_service import GooglePlacesService

    try:
        data = GooglePlacesService(settings.google_places_api_key).get_full_place_data(place_id)
    except Exception as exc:
        logger.warning("assistant: place details failed for %s: %s", place_id, exc)
        return {"error": f"Could not load that restaurant: {exc}"}, []

    place, reviews = data["place"], data["reviews"]
    dishes: list[dict] = []
    review_texts = [review.get("text", "") for review in reviews if review.get("text")]
    if review_texts and settings.deepseek_api_key:
        try:
            from app.services.dish_extractor import extract_popular_dishes

            dishes = extract_popular_dishes(review_texts, settings.deepseek_api_key, top_n=8)
        except Exception as exc:
            logger.warning("assistant: dish extraction failed for %s: %s", place_id, exc)

    hours = place.get("opening_hours") or {}
    payload = {
        "place_id": place_id,
        "name": place.get("name", ""),
        "address": place.get("formatted_address", ""),
        "rating": place.get("rating"),
        "user_ratings_total": place.get("user_ratings_total"),
        "price_level": place.get("price_level"),
        "open_now": hours.get("open_now"),
        "hours_today": (hours.get("weekday_text") or [None])[0],
        "website": place.get("website"),
        "phone": place.get("formatted_phone_number"),
        # Dishes reviewers keep naming. NOT the menu — see the note below.
        "popular_dishes": [
            {"name": dish.get("name"), "mentions": dish.get("mention_count")}
            for dish in dishes if dish.get("name")
        ],
        "menu_online": False,
    }
    # Menuist reads menus from photographs; it has no way to pull one off the web. Saying so
    # explicitly is what stops the model from presenting review chatter as "the menu", or
    # inventing plausible-sounding dishes to fill the gap.
    payload["note"] = REVIEWS_NOT_MENU if payload["popular_dishes"] else NO_REVIEW_DISHES

    # No card: this place is already in the list from the search, and replacing five results with
    # one would take away the alternatives the reply is busy suggesting.
    return payload, []


# ─── read_menu ───────────────────────────────────────────────────────────────

SAMPLE_ITEMS = 6
MAX_SUMMARY_CATEGORIES = 8
SOURCE_NAMES = {"website": "the restaurant's website"}


def _summarise(combined, restaurant_name: str, results) -> dict:
    """What the model needs to talk about the menu: where it came from, and a sample of it.

    A combined menu can run to a couple of hundred dishes (Katz's has 194). Putting all of that in
    the conversation would crowd everything else out; the full menu goes to the screen instead.
    """
    categories = []
    for category in combined.menu.menu[:MAX_SUMMARY_CATEGORIES]:
        names = [item.name_translated or item.name for item in category.items[:SAMPLE_ITEMS]]
        categories.append({"category": category.category_translated or category.category,
                           "items": names, "item_count": len(category.items)})
    return {
        "found": combined.total_items > 0,
        "restaurant": restaurant_name,
        "sources": [{"source": SOURCE_NAMES.get(r.report.kind, r.report.kind),
                     "status": r.report.status, "detail": r.report.detail} for r in results],
        "total_items": combined.total_items,
        "categories": categories,
    }


def read_menu(place_id: str) -> tuple[dict, list[RestaurantCard]]:
    """Read the menu from the restaurant's own website, and return it labelled by source.

    The combined result rides along under ``FULL_MENU_KEY`` for the agent to lift out: it belongs
    on screen, not in the prompt. On the results page the diner can add a photo of the menu, which
    is merged with it.
    """
    if not settings.google_places_api_key or not settings.deepseek_api_key:
        return {"error": "Reading menus isn't configured on this deployment."}, []

    from app.services.menu_sources.gather import gather

    restaurant, results, combined = gather(place_id)
    if all(r.report.status == "error" for r in results):
        return {"error": "Couldn't reach this restaurant's menu sources right now."}, []

    payload = _summarise(combined, restaurant, results)
    payload["place_id"] = place_id
    payload["note"] = MENU_FOUND if combined.total_items else NO_MENU_ONLINE
    payload[FULL_MENU_KEY] = {"combined": combined.model_dump(),
                              "results": [r.model_dump() for r in results]}
    return payload, []


# ─── food_knowledge ──────────────────────────────────────────────────────────


def food_knowledge(question: str) -> tuple[dict, list[RestaurantCard]]:
    """Search the local knowledge base. Costs nothing and works with no API keys at all."""
    try:
        from app.knowledge.db import knowledge_session
        from app.knowledge.retrieval import search_passages

        with knowledge_session() as db:
            hits = search_passages(db, question, top_k=MAX_KNOWLEDGE_PASSAGES)
    except Exception as exc:
        logger.warning("assistant: knowledge search failed for %r: %s", question, exc)
        return {"error": "The knowledge base is unavailable right now."}, []

    if not hits:
        return {"passages": [], "note": "Nothing in the knowledge base covers this."}, []
    return {
        "passages": [
            {
                "text": hit["text"][:PASSAGE_CHARS],
                "source": hit["document_title"],
                "license": hit["license"],
            }
            for hit in hits
        ]
    }, []


# ─── Dispatch ────────────────────────────────────────────────────────────────


def execute(name: str, arguments: dict, context: DinerContext) -> tuple[dict, list[RestaurantCard]]:
    """Run one tool call. Returns (payload for the model, cards for the UI)."""
    logger.info("assistant: tool %s(%s)", name, arguments)
    try:
        if name == "find_restaurants":
            return find_restaurants(
                what=str(arguments.get("what", "")),
                near=str(arguments.get("near", "") or ""),
                radius_km=_as_float(arguments.get("radius_km")),
                open_now=bool(arguments.get("open_now")),
                context=context,
            )
        if name == "restaurant_highlights":
            place_id = str(arguments.get("place_id", "")).strip()
            if not place_id:
                return {"error": "No place_id given. Call find_restaurants first."}, []
            return restaurant_highlights(place_id)
        if name == "read_menu":
            place_id = str(arguments.get("place_id", "")).strip()
            if not place_id:
                return {"error": "No place_id given. Call find_restaurants first."}, []
            return read_menu(place_id)
        if name == "food_knowledge":
            return food_knowledge(str(arguments.get("question", "")))
    except Exception as exc:  # a tool must never take the conversation down with it
        logger.exception("assistant: tool %s failed", name)
        return {"error": f"{name} failed: {exc}"}, []

    return {"error": f"Unknown tool {name!r}."}, []


def _as_float(value) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
