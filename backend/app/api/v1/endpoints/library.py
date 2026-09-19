"""A signed-in user's saved menus and restaurant history.

Anonymous visitors have no library: their results live only in the browser tab and are gone on
refresh. Saving happens automatically in the menu-parse and place-details endpoints when signed in.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user, require_accounts
from app.db.models import RestaurantHistory, SavedMenu, User
from app.db.session import get_db
from app.models.library import RestaurantHistoryItem, SavedMenuDetail, SavedMenuSummary
from app.models.menu import ParsedMenu

router = APIRouter(dependencies=[Depends(require_accounts)])

MAX_HISTORY_ITEMS = 50


# ─── Helpers used by other endpoints ────────────────────────────────────────────


def find_saved_menu(db: Session, user: User, image_sha256: str, target_language: str | None) -> SavedMenu | None:
    return db.scalar(select(SavedMenu).where(
        SavedMenu.user_id == user.id,
        SavedMenu.image_sha256 == image_sha256,
        SavedMenu.target_language == (target_language or ""),
    ))


def save_menu(
    db: Session, user: User, image_sha256: str, target_language: str | None,
    restaurant_name: str | None, parsed_menu: ParsedMenu, menu_id: str | None = None,
) -> SavedMenu:
    now = datetime.now(timezone.utc)
    menu_json = parsed_menu.model_dump(exclude={"menu_id"})
    item_count = sum(len(category.items) for category in parsed_menu.menu)

    saved = find_saved_menu(db, user, image_sha256, target_language)
    if saved is None:
        saved = SavedMenu(
            user_id=user.id, image_sha256=image_sha256, target_language=target_language or "",
            created_at=now,
        )
        db.add(saved)
    saved.menu_id = menu_id or saved.menu_id
    saved.restaurant_name = (restaurant_name or saved.restaurant_name or "").strip()[:255]
    saved.detected_language = parsed_menu.detected_language
    saved.item_count = item_count
    saved.parsed_menu = menu_json
    saved.updated_at = now
    db.commit()
    db.refresh(saved)
    return saved


def record_restaurant_view(db: Session, user: User, place_id: str, label: str | None) -> None:
    entry = db.scalar(select(RestaurantHistory).where(
        RestaurantHistory.user_id == user.id, RestaurantHistory.place_id == place_id
    ))
    if entry is None:
        entry = RestaurantHistory(user_id=user.id, place_id=place_id)
        db.add(entry)
    if label:
        entry.label = label.strip()[:255]
    entry.viewed_at = datetime.now(timezone.utc)
    db.commit()


# ─── Saved menus ────────────────────────────────────────────────────────────────


@router.get("/menus", response_model=list[SavedMenuSummary])
def list_menus(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(SavedMenu).where(SavedMenu.user_id == user.id)
        .order_by(SavedMenu.updated_at.desc()).limit(MAX_HISTORY_ITEMS)
    ).all()


@router.get("/menus/{menu_id}", response_model=SavedMenuDetail)
def get_menu(menu_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    saved = db.get(SavedMenu, menu_id)
    # 404 (not 403) for other users' menus, so ids can't be probed.
    if saved is None or saved.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu not found")
    return saved


@router.delete("/menus/{menu_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_menu(menu_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(delete(SavedMenu).where(SavedMenu.id == menu_id, SavedMenu.user_id == user.id))
    db.commit()


# ─── Restaurant history ─────────────────────────────────────────────────────────


@router.get("/restaurants", response_model=list[RestaurantHistoryItem])
def list_restaurants(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(RestaurantHistory).where(RestaurantHistory.user_id == user.id)
        .order_by(RestaurantHistory.viewed_at.desc()).limit(MAX_HISTORY_ITEMS)
    ).all()


@router.delete("/restaurants/{place_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_restaurant(place_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(delete(RestaurantHistory).where(
        RestaurantHistory.place_id == place_id, RestaurantHistory.user_id == user.id
    ))
    db.commit()
