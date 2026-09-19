"""Run the menu sources that are read from the internet — today, the restaurant's website.

Reviews come with the place details and uploads come from the diner, so the website is the only
source fetched here. The results page asks for it by kind (so another source can be added without
changing the page); the assistant calls ``gather``, which also combines the result.
"""

from __future__ import annotations

import logging
from typing import Iterable, NamedTuple, Optional

from app.core.config import settings
from app.models.menu_sources import (
    CombinedMenu,
    ReviewDish,
    SourceReport,
    SourceResult,
    SourcedMenu,
)
from app.services.menu_sources.merge import combine

logger = logging.getLogger(__name__)

READABLE_KINDS = ("website",)


def _error(kind: str, detail: str) -> SourceResult:
    return SourceResult(report=SourceReport(kind=kind, status="error", detail=detail))


def read_source(kind: str, place_id: str, target_language: Optional[str] = "English",
                place: Optional[dict] = None) -> SourceResult:
    """Check one source for one place. Never raises: failures come back as a report."""
    if kind not in READABLE_KINDS:
        return _error(kind, f"Unknown menu source {kind!r}.")
    if not settings.google_places_api_key or not settings.deepseek_api_key:
        return SourceResult(report=SourceReport(
            kind=kind, status="unavailable", detail="Menu lookup isn't configured on this server."))

    from app.services.google_places_service import GooglePlacesService

    service = GooglePlacesService(settings.google_places_api_key)
    try:
        place = place or service.get_menu_fields(place_id)
    except Exception as exc:
        logger.warning("menu_sources: couldn't load %s: %s", place_id, exc)
        return _error(kind, "Couldn't load this restaurant from Google.")

    try:
        from app.services.menu_sources.website import read_website_menu

        return read_website_menu(place.get("name", ""), place.get("website"),
                                 settings.deepseek_api_key, target_language)
    except Exception as exc:  # one broken source must not take the others down
        logger.exception("menu_sources: %s failed for %s", kind, place_id)
        return _error(kind, f"Something went wrong reading this source ({type(exc).__name__}).")


class Gathered(NamedTuple):
    restaurant_name: str
    results: list[SourceResult]
    combined: CombinedMenu


def gather(place_id: str, target_language: Optional[str] = "English",
           review_dishes: Iterable[ReviewDish] = ()) -> Gathered:
    """Every readable source, then the combined menu. Used by the assistant."""
    place = None
    if settings.google_places_api_key:
        from app.services.google_places_service import GooglePlacesService

        try:  # look the place up once and share it, rather than once per source
            place = GooglePlacesService(settings.google_places_api_key).get_menu_fields(place_id)
        except Exception as exc:
            logger.warning("menu_sources: couldn't load %s: %s", place_id, exc)

    results = [read_source(kind, place_id, target_language, place) for kind in READABLE_KINDS]
    sources = [SourcedMenu(kind=r.report.kind, menu=r.menu) for r in results if r.menu]
    return Gathered((place or {}).get("name", ""), results, combine(sources, review_dishes))
