"""Turn document passages into graph edges with DeepSeek (dish -> ingredient, technique, pairings).

Each extracted edge keeps a pointer to the passage it came from (evidence_chunk_id), so answers
built on the graph can cite the original text.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.knowledge.models import Chunk
from app.knowledge.store import entity_ids, entity_row, insert_edges, upsert_entities

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are building a culinary knowledge graph from a cookbook passage.

Extract only facts stated or clearly implied by the passage. Return JSON with this shape:
{{
  "dishes": [
    {{"name": "Dish name", "ingredients": ["ingredient", "..."], "techniques": ["baking", "..."]}}
  ],
  "pairings": [
    {{"a": "food or dish", "b": "food or dish", "reason": "short reason from the passage"}}
  ]
}}
Use short, generic names (e.g. "butter", not "two tablespoons of butter"). Use empty lists when nothing applies.

Passage:
\"\"\"{passage}\"\"\"
"""


def _names(values) -> list[str]:
    return [v.strip() for v in values or [] if isinstance(v, str) and v.strip()][:30]


def extract_graph(db: Session, llm_client, document_id: int, limit: int = 20) -> dict:
    """Extract edges from up to `limit` not-yet-processed chunks of a document."""
    chunks = db.scalars(
        select(Chunk).where(Chunk.document_id == document_id, Chunk.graph_extracted.is_(False))
        .order_by(Chunk.chunk_index).limit(limit)
    ).all()

    processed = edges_added = 0
    for chunk in chunks:
        text = llm_client.generate(
            EXTRACTION_PROMPT.format(passage=chunk.text), json_mode=True, cache=True,
            purpose="graph_extraction", max_tokens=1500,
        )
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Chunk %s: model returned invalid JSON; skipping", chunk.id)
            continue

        triples = []  # (src_type, src_name, relation, dst_type, dst_name)
        for dish in data.get("dishes", []) if isinstance(data.get("dishes"), list) else []:
            name = dish.get("name", "").strip() if isinstance(dish, dict) else ""
            if not name:
                continue
            triples += [("dish", name, "made_from", "ingredient", i) for i in _names(dish.get("ingredients"))]
            triples += [("dish", name, "uses_technique", "technique", t) for t in _names(dish.get("techniques"))]
        for pairing in data.get("pairings", []) if isinstance(data.get("pairings"), list) else []:
            if isinstance(pairing, dict) and pairing.get("a") and pairing.get("b"):
                triples.append(("ingredient", pairing["a"], "pairs_with", "ingredient", pairing["b"]))

        rows = [r for t in triples for r in (entity_row(t[0], t[1]), entity_row(t[3], t[4])) if r]
        upsert_entities(db, rows)
        ids = {t: entity_ids(db, t) for t in {r["type"] for r in rows}}
        edges = []
        for src_type, src_name, relation, dst_type, dst_name in triples:
            src_row, dst_row = entity_row(src_type, src_name), entity_row(dst_type, dst_name)
            if not src_row or not dst_row:
                continue
            src, dst = ids[src_type].get(src_row["normalized_name"]), ids[dst_type].get(dst_row["normalized_name"])
            if src and dst and src != dst:
                edges.append({
                    "src_id": src, "relation": relation, "dst_id": dst, "weight": 1.0,
                    "source": "llm_extraction", "evidence_chunk_id": chunk.id,
                })
        insert_edges(db, edges)
        chunk.graph_extracted = True
        db.commit()
        processed += 1
        edges_added += len(edges)

    result = {"chunks_processed": processed, "edges": edges_added}
    logger.info("Graph extraction for document %s: %s", document_id, result)
    return result
