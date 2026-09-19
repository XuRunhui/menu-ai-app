"""Wikipedia importer (CC BY-SA 4.0): articles on how food cultures structure and pair meals."""

from __future__ import annotations

import logging
import re

import requests
from sqlalchemy.orm import Session

from app.knowledge.sources.common import SOURCES_DIR, USER_AGENT
from app.knowledge.store import add_chunks, create_document
from app.knowledge.text import chunk_text

logger = logging.getLogger(__name__)

API = "https://en.wikipedia.org/w/api.php"
LICENSE = "CC BY-SA 4.0 (Wikipedia contributors)"

# Meal structures and pairing customs; chosen for combo recommendations.
MEAL_STRUCTURE_ARTICLES = [
    "Ichijū-sansai", "Kaiseki", "Bento", "Banchan", "Thali", "Sadya", "Nasi campur", "Dim sum",
    "Chinese food therapy", "Meze", "Tapas", "Italian meal structure", "Full-course dinner",
    "Smorgasbord", "Plate lunch", "Meat and three", "Value menu", "Food pairing",
    "Wine and food pairing", "Mouthfeel", "Meal",
]

# Sections that describe the article's sources rather than food.
_SKIP_SECTIONS = re.compile(r"^==+\s*(See also|References|Further reading|External links|Notes|Bibliography|Citations)\s*==+\s*$",
                            re.IGNORECASE | re.MULTILINE)


def fetch_article(title: str) -> tuple[str, str] | None:
    """Return (canonical title, plain text) or None if the article doesn't exist."""
    cache = SOURCES_DIR / "wikipedia" / f"{re.sub(r'[^A-Za-z0-9]+', '_', title)}.txt"
    if cache.exists():
        canonical, _, text = cache.read_text(encoding="utf-8").partition("\n")
        return canonical, text

    response = requests.get(API, params={
        "action": "query", "format": "json", "formatversion": 2, "redirects": 1,
        "prop": "extracts", "explaintext": 1, "titles": title,
    }, headers={"User-Agent": USER_AGENT}, timeout=60)
    response.raise_for_status()
    page = response.json()["query"]["pages"][0]
    if page.get("missing") or not page.get("extract"):
        return None

    text = page["extract"]
    cut = _SKIP_SECTIONS.search(text)
    text = text[:cut.start()] if cut else text
    # "== Heading ==" lines become paragraph breaks so chunks follow sections.
    text = re.sub(r"^==+\s*(.*?)\s*==+\s*$", r"\n\1:", text, flags=re.MULTILINE)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(f"{page['title']}\n{text}", encoding="utf-8")
    return page["title"], text


def import_wikipedia(db: Session, titles: list[str] = MEAL_STRUCTURE_ARTICLES, replace: bool = False) -> dict:
    imported, chunks, missing = 0, 0, []
    for title in titles:
        article = fetch_article(title)
        if article is None:
            missing.append(title)
            continue
        canonical, text = article
        url = f"https://en.wikipedia.org/wiki/{canonical.replace(' ', '_')}"
        document = create_document(db, "wikipedia", canonical, f"{canonical} (Wikipedia)", license=LICENSE,
                                   url=url, attribution="Wikipedia contributors", replace=replace)
        if document is None:
            continue
        chunks += add_chunks(db, document, chunk_text(text))
        imported += 1
    result = {"articles": imported, "chunks": chunks, "missing": missing}
    logger.info("Wikipedia imported: %s", result)
    return result
