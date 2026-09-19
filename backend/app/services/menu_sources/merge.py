"""Combine menus from several sources into one, remembering where each dish came from.

Deterministic on purpose: no model call. Merging a 60-dish website menu with a photographed page
and five reviews would cost several thousand output tokens as an LLM task, take a few seconds, and
could quietly drop or invent dishes. Matching names is cheap, instant, and testable, and every
source is parsed into the same language first, so names line up across sources.

Two orders matter, and they are different:

- **Structure** follows the biggest source. If the website has 60 dishes and the diner photographed
  one page, the website's categories and order form the skeleton and the photo fills in.
- **Field values** follow freshness: a photo the diner took today beats the website. When two
  sources disagree on a price, the fresher one is shown and the other is kept as an ``alt_price`` —
  often the first sign the website is out of date.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Iterable, Optional

from app.models.menu import AltPrice, MenuCategory, MenuItem, ParsedMenu
from app.models.menu_sources import (
    CombinedMenu,
    ReviewDish,
    SourceCount,
    SourcedMenu,
)

# Freshest first: this decides whose price and description are shown when sources disagree.
FRESHNESS = ("upload", "website")
MENU_KINDS = set(FRESHNESS)
REVIEW_CATEGORY = "Mentioned in reviews"

# Names this close are the same dish written slightly differently ("Kimchi Jjigae" / "Kimchi Jigae").
SAME_DISH_RATIO = 0.9
# Reviews are informal, so matching them to the menu is looser.
REVIEW_MATCH_RATIO = 0.82
# Below this many dishes from real menu sources, the menu probably isn't all there.
THIN_MENU = 12

_ITEM_CODE = re.compile(r"^\s*([#№]?[a-z]{0,2}[-.]?\d{1,3}[.)]?)\s+")
_BRACKETED = re.compile(r"[(\[（【].*?[)\]）】]")
_GENERIC_TOKENS = {"the", "a", "and", "with", "of", "our", "house", "special", "dish", "plate",
                   "soup", "rice", "noodles", "set", "combo", "meal", "small", "large", "side"}


def normalize(text: Optional[str]) -> str:
    """Lower-case, punctuation-free, item codes stripped: 'C1. LA Galbi!' -> 'la galbi'."""
    text = unicodedata.normalize("NFKC", text or "").lower().replace("&", " and ")
    text = _ITEM_CODE.sub("", text)
    text = re.sub(r"[^\w\s]", " ", text)          # \w keeps CJK, Hangul, accented letters
    return re.sub(r"\s+", " ", text).strip()


def item_code(text: Optional[str]) -> Optional[str]:
    """The menu number in front of a name, if any: '#12 Combo' -> '12', 'C1. Galbi' -> 'c1'."""
    match = _ITEM_CODE.match(unicodedata.normalize("NFKC", text or "").lower())
    return re.sub(r"[^\w]", "", match.group(1)) if match else None


def core(text: Optional[str]) -> str:
    """The name without its bracketed part: 'LA Galbi (Marinated Short Rib)' -> 'la galbi'."""
    return normalize(_BRACKETED.sub(" ", unicodedata.normalize("NFKC", text or "")))


def _names(item: MenuItem) -> list[str]:
    return [name for name in (item.name, item.name_translated) if name and name.strip()]


def _keys(item: MenuItem) -> set[str]:
    return {key for key in (normalize(name) for name in _names(item)) if key}


def _cores(item: MenuItem) -> set[str]:
    return {key for key in (core(name) for name in _names(item)) if len(key) >= 4}


def _codes(item: MenuItem) -> set[str]:
    return {code for code in (item_code(name) for name in _names(item)) if code}


def _spelling_variant(left: str, right: str) -> bool:
    """Whether two names differ only by how a word is spelled, word for word.

    Raw similarity can't tell a spelling variant from a different dish:

    - an added word is a different dish: "…Hand-Ripped Noodles" vs "…Noodles in Soup" (0.90)
    - a number or letter is a different dish: "Sandwich Number 30" vs "…300" (0.97),
      "Combination A" vs "Combination B" (0.92)
    - a different word is a different dish: "Spicy Pork Bulgogi" vs "Spicy Beef Bulgogi"

    So names must have the same words in the same places, and every word that differs must be a
    real word spelled alike ("jjigae" / "jigae").
    """
    left_words, right_words = left.split(), right.split()
    if len(left_words) != len(right_words):
        return False
    for x, y in zip(left_words, right_words):
        if x == y:
            continue
        if any(ch.isdigit() for ch in x + y) or min(len(x), len(y)) < 4:
            return False
        if SequenceMatcher(None, x, y).ratio() < 0.75:
            return False
    return True


def _similar(a: set[str], b: set[str], threshold: float) -> float:
    """How alike two dishes' names are, counting only spelling differences (see above)."""
    best = 0.0
    for left in a:
        for right in b:
            if min(len(left), len(right)) >= 5 and _spelling_variant(left, right):
                best = max(best, SequenceMatcher(None, left, right).ratio())
    return best if best >= threshold else 0.0


@dataclass
class _Contribution:
    kind: str
    item: MenuItem
    source: int      # which source object — two uploaded pages are two sources of one kind


@dataclass
class _Merged:
    category: str
    category_translated: Optional[str]
    keys: set[str]
    cores: set[str]
    codes: set[str] = field(default_factory=set)
    contributions: list[_Contribution] = field(default_factory=list)
    review_mentions: int = 0


def _size_variants(menu: ParsedMenu) -> set[str]:
    """Core names that occur more than once inside one source — sizes or styles of one dish.

    "Soup (Small)" and "Soup (Large)" share the core "soup"; matching by core would fold them into
    one. They only ever sit side by side in the same source, which is how they're recognised.
    """
    seen: dict[str, int] = {}
    for category in menu.menu:
        for item in category.items:
            for key in _cores(item):
                seen[key] = seen.get(key, 0) + 1
    return {key for key, count in seen.items() if count > 1}


def _find(merged: list[_Merged], item: MenuItem, variants: set[str],
          source: int) -> Optional[_Merged]:
    """The dish this item is another sighting of, from a different source — or None.

    Never from the same source: a menu that lists "Galbi" under both Lunch and Dinner means two
    entries (usually at two prices), and folding them together would lose one.
    """
    codes = _codes(item)
    # Menu numbers identify dishes: "#12 Combo" and "#13 Combo" are two dishes even though the
    # names match once the numbers are set aside. A number on only one side doesn't count against
    # a match ("C1. LA Galbi" on the website, "LA Galbi" in a photo).
    candidates = [entry for entry in merged
                  if all(c.source != source for c in entry.contributions)
                  and not (codes and entry.codes and not codes & entry.codes)]
    keys, cores = _keys(item), _cores(item) - variants
    for entry in candidates:
        if keys & entry.keys:
            return entry
    for entry in candidates:
        if cores and cores & (entry.cores - variants):
            return entry
    scored = [(score, entry) for entry in candidates
              if (score := _similar(keys, entry.keys, SAME_DISH_RATIO))]
    return max(scored, key=lambda pair: pair[0])[1] if scored else None


def _pick(values: Iterable) -> Optional[object]:
    return next((value for value in values if value not in (None, "", [])), None)


def _price_key(item: MenuItem) -> Optional[str]:
    if item.price is not None:
        return f"{item.price:.2f}"
    return normalize(item.price_original) or None


def _resolve(entry: _Merged) -> MenuItem:
    """Build the combined dish: freshest source wins each field, other prices are kept."""
    ranked = sorted(entry.contributions, key=lambda c: FRESHNESS.index(c.kind)
                    if c.kind in FRESHNESS else len(FRESHNESS))
    items = [c.item for c in ranked]

    chosen = next((c for c in ranked if _price_key(c.item)), None)
    alt_prices, seen_prices = [], {_price_key(chosen.item)} if chosen else set()
    for contribution in ranked:
        key = _price_key(contribution.item)
        if key and key not in seen_prices:
            seen_prices.add(key)
            alt_prices.append(AltPrice(
                source=contribution.kind, price=contribution.item.price,
                price_original=contribution.item.price_original,
                currency=contribution.item.currency))

    sources = list(dict.fromkeys(c.kind for c in ranked))
    if entry.review_mentions:
        sources.append("reviews")

    return MenuItem(
        name=_pick(i.name for i in items) or "",
        name_translated=_pick(i.name_translated for i in items),
        price=chosen.item.price if chosen else None,
        price_original=chosen.item.price_original if chosen else None,
        currency=chosen.item.currency if chosen else _pick(i.currency for i in items),
        description=_pick(i.description for i in items),
        description_translated=_pick(i.description_translated for i in items),
        spicy_level=_pick(i.spicy_level for i in items),
        allergens=list(dict.fromkeys(a for i in items for a in i.allergens)),
        dietary_tags=list(dict.fromkeys(t for i in items for t in i.dietary_tags)),
        sources=sources,
        alt_prices=alt_prices,
        review_mentions=entry.review_mentions or None,
    )


def _match_review(merged: list[_Merged], dish: ReviewDish) -> Optional[_Merged]:
    """Find the menu dish a reviewer meant. Looser than menu-to-menu matching, never ambiguous."""
    name = normalize(dish.name)
    if not name:
        return None
    for entry in merged:
        if name in entry.keys or core(dish.name) in entry.cores:
            return entry

    # "Marinated Galbi" -> "LA Galbi (Marinated Short Rib)": every word the reviewer used appears
    # in the menu name. Generic words alone ("soup") are too weak to decide on.
    words = set(name.split())
    if words - _GENERIC_TOKENS and (len(words) > 1 or len(name) >= 5):
        containing = [entry for entry in merged
                      if any(words <= set(key.split()) for key in entry.keys)]
        if len(containing) == 1:
            return containing[0]
        if containing:
            # Several dishes fit: a Tomukun reviewer's "Kimchi" could be Kimchi Pancake, Kimchi
            # Stew or the Kimchi & Porkbelly Stirfry — or, most likely, the free side dish. Any
            # pick would be a guess, and a wrong "popular" label is worse than none.
            return None

    scored = [(score, entry) for entry in merged
              if (score := _similar({name}, entry.keys, REVIEW_MATCH_RATIO))]
    return max(scored, key=lambda pair: pair[0])[1] if scored else None


def combine(sources: list[SourcedMenu], review_dishes: Iterable[ReviewDish] = ()) -> CombinedMenu:
    """Merge every source into one menu with per-dish source labels and a coverage summary."""
    usable = [s for s in sources if s.kind in MENU_KINDS and s.menu.menu]
    # Biggest source first, so its categories and ordering form the skeleton.
    structure = sorted(usable, key=lambda s: -sum(len(c.items) for c in s.menu.menu))

    merged: list[_Merged] = []
    categories: dict[str, tuple[str, Optional[str]]] = {}
    for index, source in enumerate(structure):
        variants = _size_variants(source.menu)
        for category in source.menu.menu:
            category_key = normalize(category.category_translated or category.category)
            categories.setdefault(category_key, (category.category, category.category_translated))
            for item in category.items:
                if not _names(item):
                    continue
                entry = _find(merged, item, variants, index)
                if entry is None:
                    label, translated = categories[category_key]
                    entry = _Merged(category=label, category_translated=translated,
                                    keys=set(), cores=set())
                    merged.append(entry)
                entry.keys |= _keys(item)
                entry.cores |= _cores(item) - variants
                entry.codes |= _codes(item)
                entry.contributions.append(_Contribution(source.kind, item, index))

    unmatched_reviews: list[ReviewDish] = []
    for dish in review_dishes:
        entry = _match_review(merged, dish)
        if entry is None:
            unmatched_reviews.append(dish)
        else:
            entry.review_mentions += max(1, dish.mention_count)

    # Rebuild categories in skeleton order, each holding its dishes in the order they were met.
    grouped: dict[tuple[str, Optional[str]], list[MenuItem]] = {}
    for entry in merged:
        grouped.setdefault((entry.category, entry.category_translated), []).append(_resolve(entry))
    menu_categories = [MenuCategory(category=label, category_translated=translated, items=items)
                       for (label, translated), items in grouped.items()]

    if unmatched_reviews:
        menu_categories.append(MenuCategory(category=REVIEW_CATEGORY, items=[
            MenuItem(name=dish.name, sources=["reviews"],
                     review_mentions=max(1, dish.mention_count),
                     description=None)
            for dish in unmatched_reviews
        ]))

    all_items = [item for category in menu_categories for item in category.items]
    menu = ParsedMenu(
        detected_language=_pick(s.menu.detected_language for s in structure),
        target_language=_pick(s.menu.target_language for s in structure),
        menu=menu_categories,
    )
    return CombinedMenu(
        menu=menu,
        total_items=len(all_items),
        by_source=_coverage(all_items),
        **_suggestion(all_items, uploaded=any(s.kind == "upload" for s in usable)),
    )


def _coverage(items: list[MenuItem]) -> list[SourceCount]:
    counts = []
    for kind in (*FRESHNESS, "reviews"):
        having = [item for item in items if kind in item.sources]
        if having:
            counts.append(SourceCount(kind=kind, items=len(having),
                                      only_here=sum(1 for item in having if item.sources == [kind])))
    return counts


def _suggestion(items: list[MenuItem], uploaded: bool) -> dict:
    """Whether a photo of the real menu would help, phrased for the diner. Never automatic."""
    from_menus = sum(1 for item in items if MENU_KINDS & set(item.sources))
    if uploaded:
        return {"suggest_upload": False,
                "suggestion": f"{len(items)} dishes, including the ones from your photo. "
                              "Add another page if the menu has more."}
    if from_menus == 0:
        return {"suggest_upload": True,
                "suggestion": "We couldn't find this restaurant's menu online — only dishes people "
                              "mention in reviews. A photo of the menu would give you the full list."}
    if from_menus < THIN_MENU:
        return {"suggest_upload": True,
                "suggestion": f"We found {from_menus} dishes, which looks like part of the menu. "
                              "A photo of the menu would fill in the rest."}
    return {"suggest_upload": False,
            "suggestion": f"We found {from_menus} dishes. Missing something? "
                          "Add a photo of the menu and it will be merged in."}
