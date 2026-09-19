"""Read side of the knowledge base: passage search and ingredient/pairing lookups."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.knowledge.models import Chunk, Document, Edge, Entity
from app.knowledge.text import GENERIC_INGREDIENTS, MentionMatcher, normalize_name

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_chunk_matrix: dict = {"signature": None, "ids": None, "sources": None, "matrix": None}
_vocabulary: dict = {"signature": None, "matcher": None}


def _chunk_signature(db: Session) -> tuple:
    return tuple(db.execute(select(func.count(Chunk.id), func.max(Chunk.id))).one())


def search_passages(db: Session, query: str, top_k: int = 5, sources: tuple[str, ...] | None = None) -> list[dict]:
    """Semantic search over document chunks (brute-force cosine; fine for tens of thousands).

    sources limits results to documents from those sources (e.g. ("editorial", "wikipedia")).
    """
    from sentence_transformers import SentenceTransformer

    from app.services.embeddings import get_model

    signature = _chunk_signature(db)
    if not signature[0]:
        return []
    with _lock:
        if _chunk_matrix["signature"] != signature:
            rows = db.execute(
                select(Chunk.id, Chunk.embedding, Document.source)
                .join(Document, Document.id == Chunk.document_id)
                .where(Chunk.embedding.is_not(None))
            ).all()
            _chunk_matrix.update(
                signature=signature,
                ids=np.array([r.id for r in rows]),
                sources=np.array([r.source for r in rows]),
                matrix=np.vstack([np.frombuffer(r.embedding, dtype=np.float32) for r in rows]),
            )
        ids, matrix, chunk_sources = _chunk_matrix["ids"], _chunk_matrix["matrix"], _chunk_matrix["sources"]

    model = get_model(settings.rag_embedding_model, SentenceTransformer)
    query_vector = np.asarray(model.encode([query], convert_to_numpy=True)[0], dtype=np.float32)
    query_vector /= max(float(np.linalg.norm(query_vector)), 1e-12)
    scores = matrix @ query_vector
    if sources:
        scores = np.where(np.isin(chunk_sources, list(sources)), scores, -np.inf)
    best = [i for i in np.argsort(scores)[::-1][:top_k] if np.isfinite(scores[i])]

    chunk_ids = [int(ids[i]) for i in best]
    rows = {c.id: (c, d) for c, d in db.execute(
        select(Chunk, Document).join(Document, Document.id == Chunk.document_id).where(Chunk.id.in_(chunk_ids))
    ).all()}
    results = []
    for i in best:
        chunk, document = rows[int(ids[i])]
        results.append({
            "chunk_id": chunk.id, "score": round(float(scores[i]), 4), "text": chunk.text, "page": chunk.page,
            "document_title": document.title, "url": document.url, "license": document.license,
            "source": document.source,
        })
    return results


def ingredient_matcher(db: Session) -> MentionMatcher:
    signature = db.execute(select(func.count(Entity.id), func.max(Entity.id)).where(Entity.type == "ingredient")).one()
    with _lock:
        if _vocabulary["signature"] != tuple(signature):
            vocabulary = dict(db.execute(
                select(Entity.normalized_name, Entity.id).where(Entity.type == "ingredient")
            ).all())
            _vocabulary.update(signature=tuple(signature), matcher=MentionMatcher(vocabulary))
        return _vocabulary["matcher"]


@dataclass
class DishProfile:
    name: str
    description: str = ""
    category: str = ""
    ingredient_ids: dict[int, str] = field(default_factory=dict)   # entity id -> ingredient name
    matched_dish: str | None = None


def build_dish_profile(db: Session, name: str, description: str = "", category: str = "") -> DishProfile:
    """Ingredients for a menu dish: from a matching Wikidata dish, plus names found in its text."""
    profile = DishProfile(name=name, description=description or "", category=category or "")

    dish = db.scalar(select(Entity).where(Entity.type == "dish", Entity.normalized_name == normalize_name(name)))
    if dish is not None:
        profile.matched_dish = dish.name
        for entity in db.scalars(
            select(Entity).join(Edge, Edge.dst_id == Entity.id)
            .where(Edge.src_id == dish.id, Edge.relation == "made_from")
        ):
            profile.ingredient_ids[entity.id] = entity.name

    for entity_id, phrase in ingredient_matcher(db).find(f"{name}. {description}").items():
        profile.ingredient_ids.setdefault(entity_id, phrase)

    profile.ingredient_ids = {
        eid: n for eid, n in profile.ingredient_ids.items() if normalize_name(n) not in GENERIC_INGREDIENTS
    }
    return profile


def pairing_weights(db: Session, profiles: list[DishProfile]) -> dict[tuple[int, int], float]:
    """All pairs_with weights among the given dishes' ingredients, in one query."""
    ids = sorted({eid for p in profiles for eid in p.ingredient_ids})
    weights: dict[tuple[int, int], float] = {}
    for start in range(0, len(ids), 400):
        batch = ids[start:start + 400]
        rows = db.execute(
            select(Edge.src_id, Edge.dst_id, Edge.weight).where(
                Edge.relation == "pairs_with", Edge.src_id.in_(batch), Edge.dst_id.in_(ids)
            )
        ).all()
        for src, dst, weight in rows:
            key = (min(src, dst), max(src, dst))
            weights[key] = max(weight, weights.get(key, 0.0))
    return weights


def pairing_evidence(
    a: DishProfile, b: DishProfile, weights: dict[tuple[int, int], float], limit: int = 5
) -> list[dict]:
    """Strongest ingredient pairings between two dishes (ingredients shared by both are skipped)."""
    evidence = []
    for id_a, name_a in a.ingredient_ids.items():
        for id_b, name_b in b.ingredient_ids.items():
            if id_a == id_b:
                continue
            weight = weights.get((min(id_a, id_b), max(id_a, id_b)))
            if weight:
                evidence.append({"a": name_a, "b": name_b, "weight": round(weight, 3), "source": "flavorgraph"})
    return distinct_pairings(evidence, limit)


def distinct_pairings(evidence: list[dict], limit: int = 5) -> list[dict]:
    """Strongest first, each ingredient pair once, whichever way round it was found.

    The same pair turns up more than once: two ingredient entries can share a name, and a trio
    collects evidence from each of its three dish pairs. Repeats inflated the pairing score and
    showed "soup × vegetable" twice on one combo card.
    """
    seen: set[frozenset[str]] = set()
    distinct = []
    for item in sorted(evidence, key=lambda e: e["weight"], reverse=True):
        names = frozenset((normalize_name(item["a"]), normalize_name(item["b"])))
        if len(names) < 2 or names in seen:   # "vegetable × vegetable" says nothing
            continue
        seen.add(names)
        distinct.append(item)
        if len(distinct) == limit:
            break
    return distinct


def shared_compounds(db: Session, ingredient_a: str, ingredient_b: str, limit: int = 3) -> list[str]:
    """Flavor compounds (FlavorGraph) found in both ingredients."""
    def compounds(name: str) -> set[int]:
        entity = db.scalar(select(Entity.id).where(Entity.type == "ingredient", Entity.normalized_name == normalize_name(name)))
        if entity is None:
            return set()
        return set(db.scalars(select(Edge.dst_id).where(Edge.src_id == entity, Edge.relation == "has_compound")))

    common = compounds(ingredient_a) & compounds(ingredient_b)
    if not common:
        return []
    return list(db.scalars(select(Entity.name).where(Entity.id.in_(list(common)[:limit]))))
