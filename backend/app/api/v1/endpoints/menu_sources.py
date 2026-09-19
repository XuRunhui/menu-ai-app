"""Build a restaurant's menu from its website, its reviews, and the diner's photos."""

from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from app.core.rate_limit import enforce_demo_limits
from app.models.menu_sources import CombinedMenu, CombineRequest, SourceRequest, SourceResult
from app.services.menu_sources.gather import read_source
from app.services.menu_sources.merge import combine

router = APIRouter()


@router.post("/sources/{kind}", response_model=SourceResult,
             dependencies=[Depends(enforce_demo_limits)])
async def read_menu_source(kind: Literal["website"],
                           request: SourceRequest) -> SourceResult:
    """Look for the place's menu in one source and read it.

    Called once per source so the page can show each as soon as it's ready. Always answers 200:
    "no menu on the website" or "the website isn't theirs any more" come back as a report, which
    the page shows to the diner, rather than as an error.
    """
    return await run_in_threadpool(read_source, kind, request.place_id, request.target_language)


@router.post("/combine", response_model=CombinedMenu)
def combine_menus(request: CombineRequest) -> CombinedMenu:
    """Merge per-source menus (and review dishes) into one menu with each dish's sources.

    Pure and free — no network or model calls — so the page calls it every time a source arrives
    or the diner adds a photo, sending back the source menus it holds.
    """
    return combine(request.sources, request.review_dishes)
