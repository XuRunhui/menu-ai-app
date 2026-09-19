"""Wikidata importer (CC0): dishes with their ingredients, cuisines, and countries of origin."""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

import requests
from sqlalchemy.orm import Session

from app.knowledge.sources.common import SOURCES_DIR, USER_AGENT
from app.knowledge.store import entity_ids, entity_row, insert_edges, upsert_entities

logger = logging.getLogger(__name__)

ENDPOINT = "https://query.wikidata.org/sparql"
_QID = re.compile(r"^Q\d+$")

DISH_INGREDIENTS_QUERY = """
SELECT ?dish ?dishLabel ?dishDescription ?ingredient ?ingredientLabel WHERE {
  ?dish wdt:P31 wd:Q746549 .
  ?dish wdt:P186|wdt:P527 ?ingredient .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
"""

DISH_ORIGINS_QUERY = """
SELECT ?dish ?cuisineLabel ?countryLabel WHERE {
  ?dish wdt:P31 wd:Q746549 .
  ?dish wdt:P186|wdt:P527 [] .
  OPTIONAL { ?dish wdt:P2012 ?cuisine . }
  OPTIONAL { ?dish wdt:P495 ?country . }
  FILTER(BOUND(?cuisine) || BOUND(?country))
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
"""


def _run_query(query: str, attempts: int = 3) -> list[dict]:
    # The public query service sometimes drops long responses; retry with a pause.
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(
                ENDPOINT, params={"query": query, "format": "json"},
                headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"}, timeout=180,
            )
            response.raise_for_status()
            return response.json()["results"]["bindings"]
        except (requests.RequestException, ValueError) as exc:
            if attempt == attempts:
                raise
            logger.warning("Wikidata query failed (%s); retrying in %ds", exc, 10 * attempt)
            time.sleep(10 * attempt)
    return []


def fetch(force: bool = False) -> Path:
    path = SOURCES_DIR / "wikidata" / "dishes.json"
    if path.exists() and not force:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Querying Wikidata for dishes")
    payload = {"ingredients": _run_query(DISH_INGREDIENTS_QUERY), "origins": _run_query(DISH_ORIGINS_QUERY)}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _value(binding: dict, name: str) -> str:
    value = binding.get(name, {}).get("value", "")
    return "" if _QID.match(value) else value


def _qid(binding: dict, name: str) -> str:
    return binding.get(name, {}).get("value", "").rsplit("/", 1)[-1]


def import_wikidata(db: Session, path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))

    dishes, ingredients, dish_ingredients = {}, {}, []
    for b in payload["ingredients"]:
        dish_name, ingredient_name = _value(b, "dishLabel"), _value(b, "ingredientLabel")
        if not dish_name or not ingredient_name:
            continue
        dishes[_qid(b, "dish")] = entity_row(
            "dish", dish_name, wikidata_id=_qid(b, "dish"), description=_value(b, "dishDescription")[:1000]
        )
        ingredients[_qid(b, "ingredient")] = entity_row("ingredient", ingredient_name, wikidata_id=_qid(b, "ingredient"))
        dish_ingredients.append((_qid(b, "dish"), _qid(b, "ingredient")))

    cuisines, countries, dish_origins = {}, {}, []
    for b in payload["origins"]:
        qid = _qid(b, "dish")
        if qid not in dishes:
            continue
        if cuisine := _value(b, "cuisineLabel"):
            cuisines[cuisine] = entity_row("cuisine", cuisine)
            dish_origins.append((qid, "cuisine", "cuisine", cuisine))
        if country := _value(b, "countryLabel"):
            countries[country] = entity_row("country", country)
            dish_origins.append((qid, "origin_country", "country", country))

    rows = [r for r in [*dishes.values(), *ingredients.values(), *cuisines.values(), *countries.values()] if r]
    upsert_entities(db, rows)
    ids = {t: entity_ids(db, t) for t in ("dish", "ingredient", "cuisine", "country")}

    def dish_id(qid: str) -> int | None:
        row = dishes.get(qid)
        return ids["dish"].get(row["normalized_name"]) if row else None

    edges = []
    for dish_qid, ingredient_qid in dish_ingredients:
        row = ingredients.get(ingredient_qid)
        src, dst = dish_id(dish_qid), ids["ingredient"].get(row["normalized_name"]) if row else None
        if src and dst:
            edges.append({"src_id": src, "relation": "made_from", "dst_id": dst, "weight": 1.0, "source": "wikidata"})
    for dish_qid, relation, entity_type, name in dish_origins:
        row = (cuisines if entity_type == "cuisine" else countries).get(name)
        src, dst = dish_id(dish_qid), ids[entity_type].get(row["normalized_name"]) if row else None
        if src and dst:
            edges.append({"src_id": src, "relation": relation, "dst_id": dst, "weight": 1.0, "source": "wikidata"})
    insert_edges(db, edges)

    result = {"dishes": len(dishes), "ingredients": len(ingredients), "edges": len(edges)}
    logger.info("Wikidata imported: %s", result)
    return result
