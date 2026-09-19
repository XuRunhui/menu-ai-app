"""Telling a menu that was read from one that was guessed at."""

from app.models.menu import ParsedMenu

# A parse of an unreadable board doesn't fail — it hallucinates. Real observed output for one
# menu board was seven items, four of them the identical string "Standard Drink". These two
# thresholds are what separate that from a genuine short menu.
MIN_ITEMS = 4
MIN_DISTINCT_RATIO = 0.6


def item_count(menu: ParsedMenu) -> int:
    return sum(len(category.items) for category in menu.menu)


def is_legible(menu: ParsedMenu) -> bool:
    """Whether a parse looks like a real menu rather than a guess at a blurry photograph.

    Too few items, or the same name over and over, means the model was reading texture. Reporting
    "couldn't read it" and offering to take a photo is a better answer than a menu of four
    identical drinks.
    """
    names = [item.name.strip().lower()
             for category in menu.menu for item in category.items if item.name.strip()]
    if len(names) < MIN_ITEMS:
        return False
    return len(set(names)) / len(names) >= MIN_DISTINCT_RATIO
