"""Request/response models for building a restaurant's menu out of several sources.

No single source has the whole menu. The restaurant's website often does but is sometimes stale or
not theirs any more; Google's five reviews name a handful of dishes; and the diner can photograph the
real thing. Each is read separately and labelled, then combined — see services/menu_sources/.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.models.menu import ParsedMenu

SourceKind = Literal["website", "upload", "reviews"]
# found: dishes were read. none: looked, nothing there. unavailable: couldn't look (no website, the
# site isn't the restaurant's any more, it needs a browser to load…). error: something broke.
SourceStatus = Literal["found", "none", "unavailable", "error"]


class SourceReport(BaseModel):
    """What happened when one source was checked, in words the diner can read."""

    kind: SourceKind
    status: SourceStatus
    item_count: int = 0
    detail: str = ""
    # The page the menu was read from (website only).
    url: Optional[str] = None


class SourceRequest(BaseModel):
    place_id: str = Field(..., min_length=5, max_length=300)
    # Every source is parsed into the same language, so the same dish can be matched across them.
    target_language: Optional[str] = Field("English", max_length=40)


class SourceResult(BaseModel):
    report: SourceReport
    menu: Optional[ParsedMenu] = None
    # Website only: False when the listed site no longer belongs to the restaurant (expired domains
    # get bought by unrelated sites), so the UI can stop linking to it.
    website_trusted: Optional[bool] = None


class SourcedMenu(BaseModel):
    """One source's menu, as held by the browser and sent back to be combined."""

    kind: SourceKind
    menu: ParsedMenu


class ReviewDish(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    mention_count: int = Field(1, ge=0)


class CombineRequest(BaseModel):
    sources: list[SourcedMenu] = Field(default_factory=list, max_length=12)
    review_dishes: list[ReviewDish] = Field(default_factory=list, max_length=40)


class SourceCount(BaseModel):
    kind: SourceKind
    items: int          # dishes this source contributed, including ones others also had
    only_here: int      # dishes no other source had


class CombinedMenu(BaseModel):
    menu: ParsedMenu
    total_items: int
    by_source: list[SourceCount]
    # A nudge, never a decision: whether the menu found so far looks thin enough that a photo of
    # the real one would help. The diner chooses.
    suggest_upload: bool
    suggestion: str
