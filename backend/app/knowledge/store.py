"""Write helpers shared by the knowledge importers."""

from __future__ import annotations

import logging

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.knowledge.models import Chunk, Document, Edge, Entity
from app.knowledge.text import display_name, normalize_name

logger = logging.getLogger(__name__)

SOURCE_LICENSES = {
    "wikidata": "CC0 1.0 (Wikidata)",
    "flavorgraph": "Apache-2.0 (FlavorGraph, Park et al. 2021)",
    "llm_extraction": "Derived from the cited document",
}


def _insert(db: Session, model):
    dialect = db.get_bind().dialect.name
    return (pg_insert if dialect == "postgresql" else sqlite_insert)(model)


def upsert_entities(db: Session, rows: list[dict]) -> None:
    """Insert entities, ignoring (type, normalized_name) duplicates; fill in missing external ids."""
    if not rows:
        return
    # Multi-row INSERT needs identical keys in every row.
    defaults = {"description": "", "wikidata_id": None, "flavorgraph_id": None}
    rows = [{**defaults, **row} for row in rows]
    for start in range(0, len(rows), 1000):
        batch = rows[start:start + 1000]
        db.execute(_insert(db, Entity).values(batch).on_conflict_do_nothing(
            index_elements=["type", "normalized_name"]
        ))
    for column in ("wikidata_id", "flavorgraph_id", "description"):
        updates = [r for r in rows if r.get(column)]
        for row in updates:
            entity = db.scalar(select(Entity).where(
                Entity.type == row["type"], Entity.normalized_name == row["normalized_name"]
            ))
            if entity is not None and not getattr(entity, column):
                setattr(entity, column, row[column])


def entity_row(entity_type: str, name: str, **extra) -> dict | None:
    normalized = normalize_name(name)
    if not normalized:
        return None
    return {"type": entity_type, "name": display_name(name)[:255], "normalized_name": normalized[:255], **extra}


def entity_ids(db: Session, entity_type: str) -> dict[str, int]:
    return dict(db.execute(
        select(Entity.normalized_name, Entity.id).where(Entity.type == entity_type)
    ).all())


def insert_edges(db: Session, rows: list[dict]) -> int:
    """Insert edges, ignoring exact duplicates. Returns the number of rows submitted."""
    for start in range(0, len(rows), 2000):
        db.execute(_insert(db, Edge).values(rows[start:start + 2000]).on_conflict_do_nothing(
            index_elements=["src_id", "relation", "dst_id", "source"]
        ))
    return len(rows)


def create_document(
    db: Session, source: str, external_id: str, title: str, license: str,
    url: str = "", attribution: str = "", replace: bool = False,
) -> Document | None:
    """Create a document row. Returns None if it already exists and replace is False."""
    existing = db.scalar(select(Document).where(Document.source == source, Document.external_id == external_id))
    if existing is not None:
        if not replace:
            return None
        db.delete(existing)
        db.flush()
    document = Document(
        source=source, external_id=external_id, title=title[:512],
        url=url, license=license, attribution=attribution,
    )
    db.add(document)
    db.flush()
    return document


def add_chunks(db: Session, document: Document, texts: list[str], pages: list[int | None] | None = None) -> int:
    """Embed and store chunks for a document (embeddings normalized so dot product = cosine)."""
    from sentence_transformers import SentenceTransformer

    from app.services.embeddings import embed_texts, get_model

    if not texts:
        return 0
    model_name = settings.rag_embedding_model
    model = get_model(model_name, SentenceTransformer)
    vectors = embed_texts(model, model_name, texts, use_cache=False)
    vectors = vectors / np.clip(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12, None)

    for index, (text, vector) in enumerate(zip(texts, vectors)):
        db.add(Chunk(
            document_id=document.id, chunk_index=index,
            page=pages[index] if pages else None, text=text,
            embedding=vector.astype(np.float32).tobytes(), embedding_model=model_name,
        ))
    return len(texts)


def stats(db: Session) -> dict:
    count = lambda model: db.scalar(select(func.count()).select_from(model))  # noqa: E731
    by_type = dict(db.execute(select(Entity.type, func.count()).group_by(Entity.type)).all())
    by_relation = dict(db.execute(select(Edge.relation, func.count()).group_by(Edge.relation)).all())
    return {
        "documents": count(Document),
        "chunks": count(Chunk),
        "entities": by_type,
        "edges": by_relation,
    }
