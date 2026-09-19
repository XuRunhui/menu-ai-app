"""Parsed menus from the shared cache, fetched by id to restore a results page."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.models.menu import ParsedMenu
from app.services import cache_service

router = APIRouter()


class MenuRecord(BaseModel):
    menu_id: str
    restaurant_name: str
    target_language: str
    detected_language: str | None
    item_count: int
    parsed_menu: ParsedMenu


@router.get("/{menu_id}", response_model=MenuRecord)
def get_menu(menu_id: str) -> MenuRecord:
    row = cache_service.get_menu_by_id(menu_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu not found or expired")
    return MenuRecord(
        menu_id=row.id,
        restaurant_name=row.restaurant_name,
        target_language=row.target_language,
        detected_language=row.detected_language,
        item_count=row.item_count,
        parsed_menu=ParsedMenu(**row.parsed_menu, menu_id=row.id),
    )
