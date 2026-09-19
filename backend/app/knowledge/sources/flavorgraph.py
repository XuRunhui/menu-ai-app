"""FlavorGraph importer (Apache-2.0): ingredient pairing scores and ingredient flavor compounds.

Park et al., "FlavorGraph: a large-scale food-chemical graph for generating food representations
and recommending food pairings", Scientific Reports 11, 931 (2021). https://github.com/lamypark/FlavorGraph
- ingr-ingr edges: co-occurrence scores (NPMI) from 1M+ recipes  -> relation "pairs_with"
- ingr-fcomp edges: flavor compounds found in an ingredient        -> relation "has_compound"
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.knowledge.sources.common import SOURCES_DIR, download
from app.knowledge.store import entity_ids, entity_row, insert_edges, upsert_entities

logger = logging.getLogger(__name__)

BASE_URL = "https://raw.githubusercontent.com/lamypark/FlavorGraph/master/input"
NODES_FILE = "nodes_191120.csv"
EDGES_FILE = "edges_191120.csv"


def fetch(force: bool = False) -> tuple[Path, Path]:
    folder = SOURCES_DIR / "flavorgraph"
    return (
        download(f"{BASE_URL}/{NODES_FILE}", folder / NODES_FILE, force),
        download(f"{BASE_URL}/{EDGES_FILE}", folder / EDGES_FILE, force),
    )


def import_flavorgraph(db: Session, nodes_path: Path, edges_path: Path) -> dict:
    with nodes_path.open(encoding="utf-8") as fh:
        nodes = list(csv.DictReader(fh))

    type_map = {"ingredient": "ingredient", "compound": "compound"}
    rows, node_key = [], {}
    for node in nodes:
        entity_type = type_map.get(node["node_type"])
        row = entity_row(entity_type, node["name"], flavorgraph_id=node["node_id"]) if entity_type else None
        if row:
            rows.append(row)
            node_key[node["node_id"]] = (entity_type, row["normalized_name"])
    upsert_entities(db, rows)

    ids = {t: entity_ids(db, t) for t in ("ingredient", "compound")}

    def resolve(node_id: str) -> int | None:
        key = node_key.get(node_id)
        return ids[key[0]].get(key[1]) if key else None

    relation_map = {"ingr-ingr": "pairs_with", "ingr-fcomp": "has_compound", "ingr-dcomp": "has_compound"}
    edges = []
    with edges_path.open(encoding="utf-8") as fh:
        for edge in csv.DictReader(fh):
            relation = relation_map.get(edge["edge_type"])
            src, dst = resolve(edge["id_1"]), resolve(edge["id_2"])
            if relation and src and dst and src != dst:
                weight = float(edge["score"]) if edge.get("score") not in (None, "") else 1.0
                edges.append({"src_id": src, "relation": relation, "dst_id": dst, "weight": weight, "source": "flavorgraph"})
    insert_edges(db, edges)

    result = {"entities": len(rows), "edges": len(edges)}
    logger.info("FlavorGraph imported: %s", result)
    return result

