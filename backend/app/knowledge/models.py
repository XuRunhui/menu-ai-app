"""Knowledge base schema.

- documents / chunks: source texts (cookbooks, PDFs) split into passages with embeddings, for RAG.
- entities / edges: the food graph, e.g. dish -made_from-> ingredient, ingredient -pairs_with-> ingredient.
Every document and edge records its source and license so displayed content can be attributed.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.knowledge.db import KnowledgeBase


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Document(KnowledgeBase):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("source", "external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32))          # gutenberg | pdf | text
    external_id: Mapped[str] = mapped_column(String(255))    # e.g. Gutenberg ebook id or file hash
    title: Mapped[str] = mapped_column(String(512))
    url: Mapped[str] = mapped_column(Text, default="")
    license: Mapped[str] = mapped_column(String(128))
    attribution: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Chunk(KnowledgeBase):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    embedding_model: Mapped[str] = mapped_column(String(128), default="")
    graph_extracted: Mapped[bool] = mapped_column(default=False)


class Entity(KnowledgeBase):
    __tablename__ = "entities"
    __table_args__ = (UniqueConstraint("type", "normalized_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(32))            # dish | ingredient | cuisine | country | technique
    name: Mapped[str] = mapped_column(String(255))
    normalized_name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    wikidata_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    flavorgraph_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)


class Edge(KnowledgeBase):
    __tablename__ = "edges"
    __table_args__ = (
        UniqueConstraint("src_id", "relation", "dst_id", "source"),
        Index("ix_edges_dst_relation", "dst_id", "relation"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    src_id: Mapped[int] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), index=True)
    relation: Mapped[str] = mapped_column(String(32))        # made_from | cuisine | origin_country | pairs_with | uses_technique
    dst_id: Mapped[int] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"))
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    source: Mapped[str] = mapped_column(String(32))          # wikidata | flavorgraph | llm_extraction
    evidence_chunk_id: Mapped[int | None] = mapped_column(
        ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True
    )
