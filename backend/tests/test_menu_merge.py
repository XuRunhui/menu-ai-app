"""Tests for combining menus from several sources into one labelled menu."""

from app.models.menu import MenuCategory, MenuItem, ParsedMenu
from app.models.menu_sources import ReviewDish, SourcedMenu
from app.services.menu_sources.merge import REVIEW_CATEGORY, THIN_MENU, combine


def _menu(*categories) -> ParsedMenu:
    return ParsedMenu(detected_language="English", menu=[
        MenuCategory(category=name, items=[
            item if isinstance(item, MenuItem) else MenuItem(name=item[0], price=item[1])
            for item in items])
        for name, items in categories])


def _src(kind, *categories) -> SourcedMenu:
    return SourcedMenu(kind=kind, menu=_menu(*categories))


def _items(combined):
    return {item.name: item for category in combined.menu.menu for item in category.items}


# ─── Same dish, several sources ──────────────────────────────────────────────


def test_one_dish_seen_twice_becomes_one_dish_with_both_labels():
    combined = combine([
        _src("website", ("BBQ", [("LA Galbi", 45.0), ("Bulgogi", 32.0)])),
        _src("upload", ("Grill", [("LA Galbi", 45.0)])),
    ])
    items = _items(combined)
    assert len(items) == 2
    assert items["LA Galbi"].sources == ["upload", "website"]
    assert items["Bulgogi"].sources == ["website"]


def test_the_fresher_price_wins_and_the_other_is_kept():
    # Review 4 at Brothers Galbi: "prices were higher than what's listed" — menus go stale.
    combined = combine([
        _src("website", ("BBQ", [("LA Galbi", 42.0)])),
        _src("upload", ("Grill", [("LA Galbi", 45.0)])),
    ])
    galbi = _items(combined)["LA Galbi"]
    assert galbi.price == 45.0                          # a photo taken today beats the website
    assert [(p.source, p.price) for p in galbi.alt_prices] == [("website", 42.0)]


def test_the_diners_own_photo_beats_everything():
    combined = combine([
        _src("website", ("BBQ", [("LA Galbi", 45.0)])),
        _src("upload", ("Grill", [("LA Galbi", 48.0)])),
    ])
    galbi = _items(combined)["LA Galbi"]
    assert galbi.price == 48.0 and galbi.sources == ["upload", "website"]
    assert galbi.alt_prices[0].source == "website"


def test_matching_prices_are_not_reported_as_alternatives():
    combined = combine([_src("website", ("A", [("Galbi", 45.0)])),
                        _src("upload", ("A", [("Galbi", 45.0)]))])
    assert _items(combined)["Galbi"].alt_prices == []


def test_the_biggest_source_sets_the_structure():
    combined = combine([
        _src("upload", ("Page 2", [("Naengmyeon", 18.0)])),
        _src("website", ("BBQ", [("LA Galbi", 45.0), ("Bulgogi", 32.0)]),
             ("Noodles", [("Naengmyeon", 17.0), ("Japchae", 19.0)])),
    ])
    assert [c.category for c in combined.menu.menu] == ["BBQ", "Noodles"]
    naengmyeon = _items(combined)["Naengmyeon"]
    assert naengmyeon.price == 18.0                     # …but the upload's price is shown


# ─── Telling dishes apart ────────────────────────────────────────────────────


def test_menu_codes_and_punctuation_do_not_split_a_dish():
    combined = combine([_src("website", ("A", [("C1. LA Galbi!", 45.0)])),
                        _src("upload", ("A", [("LA Galbi", 45.0)]))])
    assert combined.total_items == 1


def test_a_bracketed_description_does_not_split_a_dish():
    combined = combine([_src("website", ("A", [("LA Galbi (Marinated Short Rib)", 45.0)])),
                        _src("upload", ("A", [("LA Galbi", 45.0)]))])
    assert combined.total_items == 1


def test_sizes_of_one_dish_stay_separate():
    combined = combine([
        _src("website", ("Soup", [("Beef Soup (Small)", 12.0), ("Beef Soup (Large)", 18.0)])),
        _src("upload", ("Soup", [("Beef Soup (Large)", 18.0)])),
    ])
    items = _items(combined)
    assert set(items) == {"Beef Soup (Small)", "Beef Soup (Large)"}
    assert items["Beef Soup (Large)"].sources == ["upload", "website"]


def test_one_source_listing_a_dish_twice_keeps_both():
    combined = combine([_src("website", ("Lunch", [("LA Galbi", 29.0)]),
                                        ("Dinner", [("LA Galbi", 45.0)]))])
    assert combined.total_items == 2


def test_similar_but_different_dishes_are_not_merged():
    combined = combine([
        _src("website", ("A", [("Spicy Pork Bulgogi", 30.0),
                               ("Spicy Cumin Lamb Hand-Ripped Noodles", 14.0)])),
        _src("upload", ("A", [("Spicy Beef Bulgogi", 32.0),
                                     ("Spicy Cumin Lamb Hand-Ripped Noodles in Soup", 15.0)])),
    ])
    assert combined.total_items == 4


def test_numbered_and_lettered_dishes_are_different_dishes():
    # Found by reading a 900-dish menu in pieces: it merged down to 314.
    combined = combine([
        _src("website", ("A", [("Sandwich Number 30", 15.0), ("Combination A", 14.9),
                               ("#12 Combo", 11.0)])),
        _src("upload", ("A", [("Sandwich Number 300", 15.0), ("Combination B", 14.9),
                                     ("#13 Combo", 11.0)])),
    ])
    assert combined.total_items == 6


def test_a_spelling_variant_is_the_same_dish():
    combined = combine([_src("website", ("A", [("Kimchi Jjigae", 17.0)])),
                        _src("upload", ("A", [("Kimchi Jigae", 17.0)]))])
    assert combined.total_items == 1


def test_a_translated_name_matches_across_languages():
    korean = MenuItem(name="갈비", name_translated="Galbi", price=45.0)
    combined = combine([_src("website", ("BBQ", [("Galbi", 45.0)])),
                        _src("upload", ("구이", [korean]))])
    galbi = next(iter(_items(combined).values()))
    assert combined.total_items == 1
    # The fresher source's own name is kept, with the translation that matched it.
    assert galbi.name == "갈비" and galbi.name_translated == "Galbi"
    assert galbi.sources == ["upload", "website"]


def test_two_uploaded_pages_add_up():
    combined = combine([_src("upload", ("Page 1", [("Galbi", 45.0), ("Bulgogi", 32.0)])),
                        _src("upload", ("Page 2", [("Naengmyeon", 17.0), ("Galbi", 45.0)]))])
    items = _items(combined)
    assert set(items) == {"Galbi", "Bulgogi", "Naengmyeon"}
    assert items["Galbi"].sources == ["upload"]


# ─── Reviews ─────────────────────────────────────────────────────────────────


def test_a_dish_reviewers_mention_is_labelled_not_duplicated():
    combined = combine(
        [_src("website", ("BBQ", [("LA Galbi (Marinated Short Rib)", 45.0), ("Naengmyeon", 17.0)]))],
        [ReviewDish(name="Marinated Galbi", mention_count=2), ReviewDish(name="Naengmyeon")],
    )
    items = _items(combined)
    assert items["LA Galbi (Marinated Short Rib)"].sources == ["website", "reviews"]
    assert items["LA Galbi (Marinated Short Rib)"].review_mentions == 2
    assert REVIEW_CATEGORY not in [c.category for c in combined.menu.menu]


def test_review_dishes_not_on_the_menu_are_still_shown():
    combined = combine([_src("website", ("BBQ", [("LA Galbi", 45.0)]))],
                       [ReviewDish(name="Gold Menu")])
    review_category = combined.menu.menu[-1]
    assert review_category.category == REVIEW_CATEGORY
    assert review_category.items[0].name == "Gold Menu"
    assert review_category.items[0].sources == ["reviews"]


def test_a_generic_review_word_does_not_attach_to_a_random_dish():
    combined = combine([_src("website", ("A", [("Kimchi Soup", 12.0), ("Beef Soup", 14.0)]))],
                       [ReviewDish(name="Soup")])
    assert combined.menu.menu[-1].category == REVIEW_CATEGORY


def test_a_review_word_several_dishes_share_is_not_guessed():
    # Real case (Tomukun): reviewers said "Kimchi"; the menu has three kimchi dishes.
    combined = combine([_src("website", ("A", [("Kimchi Pancake", 18.0), ("Kimchi Stew", 17.0),
                                               ("Kimchi & Porkbelly Stirfry", 24.0)]))],
                       [ReviewDish(name="Kimchi")])
    assert all("reviews" not in item.sources for item in combined.menu.menu[0].items)
    assert combined.menu.menu[-1].category == REVIEW_CATEGORY


def test_an_exact_review_name_wins_over_dishes_that_merely_contain_it():
    combined = combine([_src("website", ("A", [("Galbi Jjim", 40.0), ("Galbi", 45.0),
                                               ("Galbi Tang", 20.0)]))],
                       [ReviewDish(name="Galbi")])
    assert _items(combined)["Galbi"].sources == ["website", "reviews"]
    assert _items(combined)["Galbi Jjim"].sources == ["website"]


# ─── Coverage and the upload nudge ───────────────────────────────────────────


def test_reviews_alone_ask_for_a_photo():
    # Exactly what Brothers Galbi showed: five review dishes and nothing else.
    combined = combine([], [ReviewDish(name=n) for n in ["Marinated Galbi", "Yukhoe", "Naengmyeon"]])
    assert combined.total_items == 3
    assert [c.category for c in combined.menu.menu] == [REVIEW_CATEGORY]
    assert combined.suggest_upload and "only dishes people mention" in combined.suggestion


def test_a_thin_menu_suggests_a_photo_and_a_full_one_does_not():
    thin = combine([_src("website", ("A", [(f"Dish {i}", 10.0) for i in range(5)]))])
    assert thin.suggest_upload and "part of the menu" in thin.suggestion

    full = combine([_src("website", ("A", [(f"Dish {i}", 10.0) for i in range(THIN_MENU + 3)]))])
    assert not full.suggest_upload and "Missing something" in full.suggestion


def test_after_an_upload_the_nudge_stops():
    combined = combine([_src("upload", ("A", [("Galbi", 45.0)]))])
    assert not combined.suggest_upload and "your photo" in combined.suggestion


def test_coverage_counts_overlap_and_unique_dishes():
    combined = combine(
        [_src("website", ("A", [("Galbi", 45.0), ("Bulgogi", 32.0), ("Japchae", 19.0)])),
         _src("upload", ("A", [("Galbi", 45.0), ("Mandu", 12.0)]))],
        [ReviewDish(name="Yukhoe")])
    counts = {c.kind: (c.items, c.only_here) for c in combined.by_source}
    assert counts == {"upload": (2, 1), "website": (3, 2), "reviews": (1, 1)}
    assert combined.total_items == 5


def test_empty_sources_are_ignored():
    assert combine([_src("website"), _src("upload", ("A", [("Galbi", 45.0)]))]).total_items == 1
