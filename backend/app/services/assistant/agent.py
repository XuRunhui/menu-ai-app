"""The dining assistant's conversation loop.

There are two ways to answer, and the assistant uses whichever it can:

**Scripted.** Three questions decide almost every dinner: what do you feel like, where are you, and
how far will you go. A state machine can ask those and run the search itself, with no model and no
token spend. This runs when there is no ``DEEPSEEK_API_KEY``, and when the model call fails — so
the demo still finds restaurants when the API key runs out of credit, which is exactly when a
recruiter is most likely to be looking at it.

**Model-driven.** With a key, DeepSeek runs the conversation and calls the tools in
``tools.py`` itself: it can search, look a restaurant up in detail, and consult the knowledge base,
in whatever order the conversation needs. It handles everything the script can't — "something warm
but not heavy", "what's good there for someone who doesn't eat pork", "is that walkable?".

The quick-reply chips are worked out from the conversation state in both paths, never by the model.
They cost nothing, they can't contradict the question that was just asked, and they give the
visitor something to tap instead of type.

Nothing is persisted: no transcript, no Google Places content, no LLM cache entry. The browser
holds the conversation and sends it back each turn.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

from app.core.config import settings
from app.models.assistant import (
    AssistantRequest,
    AssistantResponse,
    ChatMessage,
    DinerContext,
    FoundMenu,
    MenuUploadOffer,
    RestaurantCard,
)
from app.models.menu_sources import CombinedMenu, SourceResult
from app.services.assistant.tools import (
    DEFAULT_RADIUS_KM,
    FULL_MENU_KEY,
    TOOL_SCHEMAS,
    execute,
    find_restaurants,
    parse_distance,
)

logger = logging.getLogger(__name__)

# Each round is one model call plus its tool calls; three is enough for search → details → answer.
MAX_TOOL_ROUNDS = 3
# How much of the conversation the model is shown each turn. The browser keeps more than this
# (see MAX_TRANSCRIPT_MESSAGES) so that scrolling back still shows what was said.
MAX_HISTORY_MESSAGES = 30
# Must stay at or below AssistantRequest's cap, or the transcript we hand back is rejected when
# the browser sends it in again.
MAX_TRANSCRIPT_MESSAGES = 60
REPLY_TOKENS = 700
# ChatMessage caps content at 8000 characters, and the transcript is round-tripped through the
# browser, so an unusually large tool payload has to be cut rather than fail validation later.
MAX_TOOL_RESULT_CHARS = 7500

GREETING = ("Hi — I'm the Menuist dining assistant. What are you in the mood for today? "
            "A cuisine, a dish, or just a mood like “warm and cheap” all work.")
ASK_LOCATION = ("Good choice. Where are you right now? A neighbourhood, city or postcode is enough "
                "— or share your location and I'll measure the distances properly.")
ASK_RADIUS = "And how far are you willing to go — walking distance, a short drive, or further?"


@dataclass
class Profile:
    """The three things the assistant needs before it can search."""

    craving: str = ""
    near: str = ""
    radius_km: Optional[float] = None

    @property
    def ready(self) -> bool:
        return bool(self.craving and self.near and self.radius_km)


def read_profile(messages: list[ChatMessage], context: DinerContext) -> Profile:
    """Work out what is known, from the browser's context first and the transcript second.

    The scripted flow asks for the three slots in a fixed order, so the visitor's replies line up
    with the slots that weren't already answered by the browser (shared coordinates, say).
    """
    answers = [m.content.strip() for m in messages if m.role == "user" and m.content.strip()]
    position = 0
    profile = Profile()

    if answers:
        profile.craving = answers[position]
        position += 1

    if context.latitude is not None and context.longitude is not None:
        profile.near = context.location_text or "your current location"
    elif context.location_text:
        profile.near = context.location_text
    elif position < len(answers):
        profile.near = answers[position]
        position += 1

    if context.radius_km:
        profile.radius_km = context.radius_km
    elif position < len(answers):
        # Fall back to a default rather than re-asking: an unparseable answer must still move the
        # conversation forward, or the script asks the same question forever.
        profile.radius_km = parse_distance(answers[position]) or DEFAULT_RADIUS_KM

    return profile


FOUND_CHIPS = ["Tell me what to order", "Somewhere cheaper", "A different cuisine"]


def scripted_quick_replies(profile: Profile, found_any: bool) -> list[str]:
    """Tappable answers for the scripted flow, which knows exactly which question it just asked."""
    if not profile.craving:
        return ["Something spicy", "Comfort food", "Light and healthy", "Surprise me"]
    if not profile.near:
        return ["Use my location"]
    if not profile.radius_km:
        return ["Walking distance", "10 minute drive", "Half an hour is fine"]
    if found_any:
        return FOUND_CHIPS
    return ["Search a wider area", "A different cuisine", "Start over"]


def model_quick_replies(context: DinerContext, found_any: bool) -> list[str]:
    """Chips for the model-driven flow, offered only where the answer is obvious.

    The model asks its own questions ("Korean, Thai, or Mexican?"), and guessing chips for a
    question we didn't write produces answers that don't fit it. So: offer the one thing the
    browser can do that typing can't, offer the obvious follow-ups once there are results, and
    otherwise stay out of the way.
    """
    if context.latitude is None and not context.location_text:
        return ["Use my location"]
    return FOUND_CHIPS if found_any else []


def _found_menu(payload: dict) -> Optional[FoundMenu]:
    """Take the combined menu out of a tool result, leaving the summary behind.

    ``read_menu`` returns everything it read so the UI can show it, but a full menu is dozens to
    hundreds of dishes; leaving it in the tool result would crowd the conversation out of the
    context window. Removing it here is what keeps the prompt small.
    """
    data = payload.pop(FULL_MENU_KEY, None)
    if not data:
        return None
    try:
        combined = CombinedMenu(**data["combined"])
        if not combined.total_items:
            return None  # nothing to show: the upload offer covers this case
        return FoundMenu(
            restaurant_name=payload.get("restaurant", ""),
            place_id=payload.get("place_id", ""),
            combined=combined,
            results=[SourceResult(**result) for result in data["results"]],
        )
    except Exception:
        logger.warning("assistant: could not read the combined menu back", exc_info=True)
        return None

def _menu_offer(tool_name: str, payload: dict, reviews_seen: bool) -> Optional[MenuUploadOffer]:
    """Offer to read a menu photo, but only once we actually know there is no menu to find.

    This fires on ``read_menu`` coming back empty from every source and nothing else: that is the
    moment the menu is genuinely unavailable. Offering it after a mere details lookup would be jumping the
    gun — the photos haven't been checked yet. Worked out here rather than asked of the model:
    it costs nothing and can't be forgotten halfway through a conversation.
    """
    if tool_name != "read_menu" or payload.get("error") or payload.get("found") is not False:
        return None
    return MenuUploadOffer(
        restaurant_name=payload.get("restaurant", ""),
        place_id=payload.get("place_id", ""),
        # Softer wording when the diner has at least been given the dishes reviewers name.
        reason="reviews_only" if reviews_seen else "no_menu_online",
    )


def already_found_places(messages: list[ChatMessage]) -> bool:
    """Whether an earlier turn already put restaurants on screen.

    Looking one restaurant up in detail returns no new cards, but the previous results are still
    displayed — so the follow-up chips have to survive that turn instead of blinking out.
    """
    for message in messages:
        if message.role == "tool" and message.name == "find_restaurants" and message.content:
            try:
                if json.loads(message.content).get("results"):
                    return True
            except json.JSONDecodeError:
                continue
    return False


# ─── Scripted path ───────────────────────────────────────────────────────────


def _summarise(cards: list[RestaurantCard], profile: Profile, note: str) -> str:
    if note:
        return note
    if not cards:
        return (f"I couldn't find anywhere serving {profile.craving} within "
                f"{profile.radius_km:g} km of {profile.near}. Want me to widen the search?")

    lines = [f"Here's what I found for {profile.craving} near {profile.near}:"]
    for card in cards:
        details = []
        if card.rating:
            details.append(f"{card.rating}★")
        if card.distance_km is not None:
            details.append(f"{card.distance_km:g} km away")
        if card.price_level:
            details.append("$" * card.price_level)
        lines.append(f"• {card.name}" + (f" — {', '.join(details)}" if details else ""))
    lines.append("Open one to see its menu and what reviewers recommend.")
    return "\n".join(lines)


def run_scripted(request: AssistantRequest) -> AssistantResponse:
    """Answer without a model: ask for each missing slot, then search."""
    profile = read_profile(request.messages, request.context)

    if not profile.craving:
        reply, cards = GREETING, []
    elif not profile.near:
        reply, cards = ASK_LOCATION, []
    elif not profile.radius_km:
        reply, cards = ASK_RADIUS, []
    else:
        payload, cards = find_restaurants(
            what=profile.craving, near=profile.near,
            radius_km=profile.radius_km, context=request.context)
        reply = _summarise(cards, profile, payload.get("error") or payload.get("note", ""))
        if payload.get("note") and cards:
            reply = _summarise(cards, profile, "") + f"\n\n{payload['note']}"

    return AssistantResponse(
        reply=reply,
        messages=_transcript(request.messages, [ChatMessage(role="assistant", content=reply)]),
        restaurants=cards,
        quick_replies=scripted_quick_replies(profile, bool(cards)),
        llm_available=False,
        needs_location=not profile.near,
    )


# ─── Model-driven path ───────────────────────────────────────────────────────


def _system_prompt(context: DinerContext) -> str:
    known = []
    if context.latitude is not None and context.longitude is not None:
        known.append(f"- Their coordinates are {context.latitude:.4f}, {context.longitude:.4f}, "
                     "so find_restaurants can measure real distances. Don't ask where they are.")
    if context.location_text:
        known.append(f"- They said they are near: {context.location_text}")
    if context.radius_km:
        known.append(f"- They are willing to travel about {context.radius_km:g} km.")
    known_block = "\n".join(known) or "- Nothing yet. You will need to ask."

    return f"""You are Menuist's dining assistant. You help one person decide what to eat right now, \
and where to go for it. Today is {date.today():%A, %d %B %Y}.

Three things decide almost every meal: what they feel like eating, where they are, and how far \
they are willing to travel. Collect those, then call find_restaurants. Don't interrogate them — \
ask at most one short question per reply, and if they have already implied an answer, use it. \
Once you know roughly what they want and where they are, search straight away rather than asking \
another question; you can refine afterwards with real places in front of you.

If they name a restaurant you have no place_id for, call find_restaurants with that name to find \
it before answering anything about it. Never say you can't help because you haven't searched yet \
— searching is your job, not theirs.

Rules:
- Keep replies to two to four sentences. No headings, no long lists. Name at most five places.
- Never invent a restaurant, rating, price, distance or opening time. Every fact comes from a tool.
- Mention distance whenever you know it. They told you how far they'd go; show that you listened.
- If a tool result has an "error" field, say plainly what went wrong and offer what you still can.
- Use food_knowledge to explain why something suits them. It is free and offline, so prefer it \
over guessing about a cuisine or a pairing.
- Once they pick a place, call restaurant_highlights and tell them what reviewers order there.
- Anything about the menu — what they serve, what's on it, what it costs — means calling \
read_menu, which reads the restaurant's own website. Never answer those from reviews, and never \
say a menu isn't available until read_menu has looked and come back empty. When it finds nothing, \
say so plainly and offer to read a photo of the menu they take themselves, which Menuist will \
parse and translate.
- restaurant_highlights is for hours, price level and what reviewers order. That is not a menu: \
never call it "the menu", and never invent menu items.
- The places you name are also shown as cards next to your reply, so don't repeat their addresses.

What you already know about this diner:
{known_block}"""


def _assistant_dict(message) -> dict:
    """The parts of a model reply worth sending back, in the shape the API accepts.

    Built field by field rather than dumped wholesale: providers add extras (refusals, reasoning
    traces) that the next request would reject.
    """
    entry: dict = {"role": "assistant", "content": message.content or ""}
    calls = getattr(message, "tool_calls", None)
    if calls:
        entry["tool_calls"] = [
            {"id": call.id, "type": "function",
             "function": {"name": call.function.name, "arguments": call.function.arguments}}
            for call in calls
        ]
    return entry


def _tail(messages: list[ChatMessage], limit: int) -> list[ChatMessage]:
    """Keep the last ``limit`` messages, starting at a user turn.

    A window that opens on a tool result, or on an assistant turn whose tool results were cut off,
    is rejected by the API, so the start is walked forward to the first user message.
    """
    window = messages[-limit:]
    start = next((i for i, m in enumerate(window) if m.role == "user"), len(window))
    return window[start:]


def _transcript(previous: list[ChatMessage], additions: list[ChatMessage]) -> list[ChatMessage]:
    """The conversation to hand back to the browser: everything so far, capped at what it may send."""
    return _tail(list(previous) + additions, MAX_TRANSCRIPT_MESSAGES)


def run_with_model(request: AssistantRequest, llm) -> AssistantResponse:
    """Let DeepSeek run the conversation, calling tools as it needs them."""
    window = _tail(request.messages, MAX_HISTORY_MESSAGES)
    conversation: list[dict] = [{"role": "system", "content": _system_prompt(request.context)}]
    conversation += [message.model_dump(exclude_none=True) for message in window]
    turn_starts_at = len(conversation)

    cards: list[RestaurantCard] = []
    tools_used: list[str] = []
    menu_upload: Optional[MenuUploadOffer] = None
    found_menu: Optional[FoundMenu] = None
    reviews_seen = False

    for round_number in range(MAX_TOOL_ROUNDS + 1):
        # On the last round the tools are taken away, so the model has to write its answer.
        out_of_rounds = round_number == MAX_TOOL_ROUNDS
        message = llm.chat(
            conversation,
            tools=TOOL_SCHEMAS,
            tool_choice="none" if out_of_rounds else "auto",
            max_tokens=REPLY_TOKENS,
        )
        if message is None:
            break

        conversation.append(_assistant_dict(message))
        calls = list(getattr(message, "tool_calls", None) or [])
        if not calls:
            break

        for call in calls:
            name = call.function.name
            try:
                arguments = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
            payload, new_cards = execute(name, arguments, request.context)
            tools_used.append(name)
            if new_cards:
                cards = new_cards            # only a search changes the list; the newest one wins
            found_menu = _found_menu(payload) or found_menu
            reviews_seen = reviews_seen or bool(payload.get("popular_dishes"))
            menu_upload = _menu_offer(name, payload, reviews_seen) or menu_upload
            conversation.append({
                "role": "tool", "tool_call_id": call.id, "name": name,
                "content": json.dumps(payload, ensure_ascii=False)[:MAX_TOOL_RESULT_CHARS],
            })

    # Only this turn's entries are new; the browser already holds everything before them, and
    # keeps more history than the model is shown.
    added = [ChatMessage(**entry) for entry in conversation[turn_starts_at:]]
    transcript = _transcript(request.messages, added)
    reply = next((m.content for m in reversed(added) if m.role == "assistant" and m.content), "")

    return AssistantResponse(
        reply=reply or "Sorry — I lost my train of thought there. Could you say that again?",
        messages=transcript,
        restaurants=cards,
        quick_replies=model_quick_replies(
            request.context, bool(cards) or already_found_places(request.messages)),
        tools_used=tools_used,
        llm_available=True,
        needs_location=(request.context.latitude is None and not request.context.location_text),
        menu_upload=menu_upload,
        found_menu=found_menu,
    )


# ─── Entry point ─────────────────────────────────────────────────────────────


def respond(request: AssistantRequest) -> AssistantResponse:
    """Answer one turn, with the model if there is one and by script if there isn't."""
    if not settings.deepseek_api_key:
        return run_scripted(request)

    from app.services.llm_client import LLMClient

    try:
        return run_with_model(request, LLMClient(api_key=settings.deepseek_api_key))
    except Exception as exc:
        # Out of credit, rate-limited, timed out: still find them somewhere to eat.
        logger.warning("assistant: model turn failed (%s); falling back to the scripted flow", exc)
        return run_scripted(request)
