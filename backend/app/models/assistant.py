"""Request/response models for the AI dining assistant.

The conversation is **stateless on the server**: the browser holds the transcript and sends it
back with every turn, and the server returns the updated transcript. That matches how the rest of
the demo works in guest mode — refreshing the page ends the conversation, and nothing about what
someone asked for is written to disk. It also means one container can serve everyone without
keeping per-visitor state in memory.
"""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.models.menu_sources import CombinedMenu, SourceResult


class ChatMessage(BaseModel):
    """One entry in the transcript, in the shape DeepSeek's chat API expects.

    ``tool_calls`` and ``tool_call_id`` are carried through untouched so that a later turn can
    still see what a tool returned earlier — that is what makes "what about the second one?" work.
    """

    role: Literal["user", "assistant", "tool"]
    content: str = Field("", max_length=8000)
    tool_calls: Optional[list[dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


class DinerContext(BaseModel):
    """What the browser knows about the diner, sent fresh each turn.

    Coordinates arrive only if the visitor granted location permission; ``location_text`` is what
    they typed instead. Either is enough to search, but coordinates also give real distances.
    """

    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    location_text: str = Field("", max_length=200)
    radius_km: Optional[float] = Field(None, gt=0, le=100)


class AssistantRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=60)
    context: DinerContext = DinerContext()


class RestaurantCard(BaseModel):
    """A place the assistant found, rendered as a card the visitor can open in the normal flow."""

    place_id: str
    name: str
    address: str = ""
    rating: Optional[float] = None
    user_ratings_total: Optional[int] = None
    price_level: Optional[int] = None
    open_now: Optional[bool] = None
    distance_km: Optional[float] = None


class FoundMenu(BaseModel):
    """A restaurant's menu as the assistant assembled it from every source, labelled by source.

    ``results`` carries each source's own menu and report, so the results page can show where
    each dish came from and merge in a photo the diner adds later.
    """

    restaurant_name: str
    place_id: str
    combined: CombinedMenu
    results: list[SourceResult]

class MenuUploadOffer(BaseModel):
    """Set when the diner is asking about food at a place whose menu Menuist doesn't have.

    Menuist has no way to fetch a restaurant's menu from the web — it reads menus from photos.
    Rather than let the conversation trail off, the UI offers to parse one they take themselves.
    """

    restaurant_name: str
    place_id: str
    # "no_menu_online": nothing at all was found. "reviews_only": dishes reviewers name, not a menu.
    reason: Literal["no_menu_online", "reviews_only"]


class AssistantResponse(BaseModel):
    reply: str
    # The transcript to send back next turn, including any tool calls and their results.
    messages: list[ChatMessage]
    restaurants: list[RestaurantCard] = []
    # Tappable answers to whatever was just asked. Worked out from the conversation, not the model,
    # so they cost nothing and are always consistent with the question.
    quick_replies: list[str] = []
    tools_used: list[str] = []
    # False when no DEEPSEEK_API_KEY is configured: the scripted flow answered instead.
    llm_available: bool = True
    # Set when the visitor should be asked for browser location permission.
    needs_location: bool = False
    # Set when the UI should offer to read a menu photo, because there is no menu to show.
    menu_upload: Optional[MenuUploadOffer] = None
    # Set when read_menu found dishes in at least one source.
    found_menu: Optional[FoundMenu] = None
