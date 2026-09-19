"""Response models for a signed-in user's saved menus and restaurant history."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.menu import ParsedMenu


class SavedMenuSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    menu_id: str | None
    restaurant_name: str
    target_language: str
    detected_language: str | None
    item_count: int
    created_at: datetime
    updated_at: datetime


class SavedMenuDetail(SavedMenuSummary):
    parsed_menu: ParsedMenu


class RestaurantHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    place_id: str
    label: str
    viewed_at: datetime
