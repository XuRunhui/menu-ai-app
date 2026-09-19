"""Request/response models for building a restaurant's menu out of several sources.

No single source has the whole menu. The restaurant's website often does but is sometimes stale or
not theirs any more; Google's five reviews name a handful of dishes; and the diner can photograph the
real thing. Each is read separately and labelled, then combined — see services/menu_sources/.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

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


# Merging compares dishes pairwise, so its time grows with the square of the dish count: 4 menus
# of 3,000 dishes took 192 s of CPU. Real restaurants stay far below these; the largest menu read
# so far was 61 dishes.
MAX_COMBINED_DISHES = 800
MAX_DISH_TEXT = 2000


class CombineRequest(BaseModel):
    sources: list[SourcedMenu] = Field(default_factory=list, max_length=12)
    review_dishes: list[ReviewDish] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def _within_limits(self) -> "CombineRequest":
        items = [item for source in self.sources for category in source.menu.menu for item in category.items]
        if len(items) > MAX_COMBINED_DISHES:
            raise ValueError(f"at most {MAX_COMBINED_DISHES} dishes can be combined at once")
        for item in items:
            texts = (item.name, item.name_translated, item.description, item.description_translated)
            if len(item.name) > 300 or any(text and len(text) > MAX_DISH_TEXT for text in texts):
                raise ValueError("a dish's name or description is too long")
        return self


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
