"""Where dish photos come from.

Two providers, tried in order:
1. DuckDuckGo image search — most specific (can find the actual restaurant's dish). It answers
   from Google Cloud too (90 of 90 menu-paced searches in a test), but only with the ddgs/primp
   versions pinned in pyproject.toml, and it asks a fast searcher to slow down (see
   DishImageService.THROTTLE_SIGNS).
2. Wikimedia Commons — returns CC-licensed or public-domain photos of the dish itself, for what
   DuckDuckGo misses. Results carry an attribution string that the UI shows.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import requests

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "Menuist/0.1 (dish images; https://github.com/XuRunhui/menu-ai-app)"

# Searching a Chinese dish name with the English word "food" returns unrelated pictures, so the
# keyword has to match the script the dish name is written in.
_SCRIPT_KEYWORDS = [
    (re.compile(r"[가-힯]"), "음식"),          # Hangul (Korean)
    (re.compile(r"[぀-ヿ]"), "料理"),          # Hiragana / katakana (Japanese)
    (re.compile(r"[一-鿿]"), "美食"),          # Han characters (Chinese)
    (re.compile(r"[Ѐ-ӿ]"), "еда"),           # Cyrillic
    (re.compile(r"[؀-ۿ]"), "طعام"),          # Arabic
]
DEFAULT_KEYWORD = "food"

# Menu bookkeeping that isn't part of the dish: item codes and "combo/set/platter" style words.
_ITEM_CODE = re.compile(r"^\s*[#№]?[A-Za-z]{0,2}[-.]?\d{1,3}[.)]?\s+")
_GENERIC_WORDS = re.compile(
    r"\b(combo|set|platter|meal|lunch|dinner|special|plate|order|size|regular|large|small|"
    r"served with|w/|choice of)\b", re.IGNORECASE)
_GENERIC_CJK = re.compile(r"(套餐|定食|セット|정식|세트)")


def food_keyword(dish_name: str) -> str:
    """Pick a 'food' word in the same script as the dish name."""
    for pattern, keyword in _SCRIPT_KEYWORDS:
        if pattern.search(dish_name):
            return keyword
    return DEFAULT_KEYWORD


def core_dish_name(dish_name: str) -> str:
    """'C1 Galbi Combo' -> 'Galbi'; '石锅拌饭套餐' -> '石锅拌饭'. Falls back to the original."""
    name = _ITEM_CODE.sub("", dish_name)
    name = _GENERIC_CJK.sub("", name)
    name = _GENERIC_WORDS.sub(" ", name)
    name = re.sub(r"\s+", " ", name.strip(" -–—/,·")).strip()
    return name or dish_name.strip()


def build_queries(restaurant_name: str, dish_name: str) -> list[str]:
    """Web-search queries, most specific first."""
    keyword = food_keyword(dish_name)
    dish = dish_name.strip()
    core = core_dish_name(dish_name)
    restaurant = restaurant_name.strip()

    queries = []
    if restaurant:
        queries.append(f"{restaurant} {dish} {keyword}")
    queries.append(f"{dish} {keyword}")
    if core.lower() != dish.lower():
        queries.append(f"{core} {keyword}")
    return queries


_NON_LATIN = re.compile(r"[^\x00-\x7f\u00c0-\u024f]")   # beyond ASCII and accented Latin
_BRACKETS_AND_QUOTES = re.compile(r"[\"“”()\[\]（）【】]")


def commons_queries(dish_name: str, restaurant_name: str = "", translated_name: str = "") -> list[str]:
    """Queries for Wikimedia Commons, most specific first.

    Commons search requires every word to match, so the web-search queries above fail there:
    "Zingerman's Delicatessen #2 Zingerman's Reuben food" finds nothing, while "Reuben" does. So:
    no "food" keyword, no restaurant or possessive brand words ("Rick's", "Binny's"), no menu
    numbers, then the dish type on its own ("…Fried Chicken Wings" -> "Chicken Wings"), then the
    name in its own script, which is how Commons files for Chinese or Korean dishes are titled.
    Measured on 97 dishes: 34% -> 65% of dishes found.
    """
    from app.services.menu_sources.website import name_tokens

    # Only the words that identify this restaurant: "Tomukun Korean BBQ" drops "tomukun" but keeps
    # "Korean", because "Korean Fried Chicken" is a dish of its own.
    brand = set(name_tokens(restaurant_name or ""))
    names = [name.strip() for name in (translated_name, dish_name) if name and name.strip()]
    latin = next((name for name in names if not _NON_LATIN.search(name)), "")
    native = [name for name in names if _NON_LATIN.search(name)]

    queries = []
    words = [word for word in re.findall(r"[\w'’-]+", _BRACKETS_AND_QUOTES.sub(" ", core_dish_name(latin)))
             if not re.search(r"['’]s$", word, re.I) and re.sub(r"['’]", "", word.lower()) not in brand
             and not any(ch.isdigit() for ch in word)] if latin else []
    if words:
        queries.append(" ".join(words))
        if len(words) > 2:
            queries.append(" ".join(words[-2:]))
    for name in native:
        queries.append(core_dish_name(name.split("|")[0]).strip())
    return list(dict.fromkeys(q for q in queries if q))[:3]


@dataclass
class ImageCandidate:
    url: str
    source: str                 # "duckduckgo" | "wikimedia"
    width: int = 0
    attribution: str = ""       # shown next to the photo when the license requires credit


DUCKDUCKGO_TIMEOUT = 8  # seconds; fail fast and move on to the next query or provider


def search_duckduckgo(query: str, max_results: int) -> list[ImageCandidate]:
    from ddgs import DDGS

    # DuckDuckGo only. With the default backend ("auto"), ddgs silently answers from Bing when
    # DuckDuckGo fails, so a broken DuckDuckGo went unnoticed for three deploys while the photos got
    # worse. A failure here is logged and the next provider takes over instead.
    rows = DDGS(timeout=DUCKDUCKGO_TIMEOUT).images(
        query, max_results=max_results, type_image="photo", safesearch="on", backend="duckduckgo")
    return [
        ImageCandidate(url=row["image"], source="duckduckgo", width=int(row.get("width") or 0))
        for row in rows if row.get("image")
    ]


def _plain_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", value or "")).strip()


def search_wikimedia(query: str, max_results: int) -> list[ImageCandidate]:
    """Search Wikimedia Commons; results are CC-licensed or public domain, with credit required."""
    response = requests.get(COMMONS_API, params={
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": max_results,
        "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": 800,
    }, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()

    candidates = []
    for page in ((response.json().get("query") or {}).get("pages") or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        url = info.get("thumburl") or info.get("url")
        if not url:
            continue
        meta = info.get("extmetadata") or {}
        artist = _plain_text((meta.get("Artist") or {}).get("value", ""))
        license_name = _plain_text((meta.get("LicenseShortName") or {}).get("value", ""))
        credit = " · ".join(part for part in [artist[:80], license_name] if part)
        candidates.append(ImageCandidate(
            url=url, source="wikimedia", width=int(info.get("thumbwidth") or 0),
            attribution=f"{credit} · Wikimedia Commons" if credit else "Wikimedia Commons",
        ))
    return candidates
