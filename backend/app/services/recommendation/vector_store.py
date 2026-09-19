"""Simple in-memory vector store for RAG."""

import numpy as np
from typing import List, Dict, Optional
import logging

from app.services.embeddings import embed_texts, get_model

logger = logging.getLogger(__name__)

# Resolved on first use: importing sentence-transformers loads PyTorch, which adds seconds to every
# cold start even though only restaurant search needs embeddings. (Tests may patch this attribute.)
SentenceTransformer = None


def _sentence_transformer_class():
    global SentenceTransformer
    if SentenceTransformer is None:
        from sentence_transformers import SentenceTransformer as model_class
        SentenceTransformer = model_class
    return SentenceTransformer


class VectorStore:
    """In-memory vector store using sentence-transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize with a sentence transformer model.

        Args:
            model_name: HuggingFace model name (lightweight by default)
        """
        self.model_name = model_name
        # Shared across all restaurants' vector stores instead of loading a copy per restaurant.
        self.model = get_model(model_name, _sentence_transformer_class())
        self.documents = []
        self.embeddings = None

    def add_documents(self, documents: List[Dict]):
        """Add documents to the vector store.

        Args:
            documents: List of dicts with 'text', 'dish', 'metadata'
        """
        if not documents:
            logger.warning("No documents to add")
            return

        self.documents.extend(documents)

        # Create embeddings for all documents
        texts = [doc["text"] for doc in self.documents]
        logger.info(f"Creating embeddings for {len(texts)} documents...")

        # Previously seen texts come from the embedding cache; only new ones are encoded.
        self.embeddings = embed_texts(self.model, self.model_name, texts)

        logger.info(f"Embeddings created: shape {self.embeddings.shape}")

    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_dish: Optional[str] = None
    ) -> List[Dict]:
        """Semantic search for relevant documents.

        Args:
            query: Search query
            top_k: Number of results
            filter_dish: Optional dish name to filter results

        Returns:
            List of most relevant documents with scores
        """
        if self.embeddings is None or len(self.embeddings) == 0:
            logger.warning("No embeddings available for search")
            return []

        # Encode query
        query_embedding = self.model.encode([query], convert_to_numpy=True)[0]

        # Calculate cosine similarity
        similarities = np.dot(self.embeddings, query_embedding) / (
            np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_embedding)
        )

        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k * 3]  # Get extra for filtering

        # Filter and format results
        results = []
        for idx in top_indices:
            doc = self.documents[idx]

            # Apply dish filter if specified
            if filter_dish and doc.get("dish") != filter_dish:
                continue

            results.append({
                **doc,
                "score": float(similarities[idx])
            })

            if len(results) >= top_k:
                break

        logger.info(f"Search completed: found {len(results)} results for query: {query[:50]}...")
        return results

    def clear(self):
        """Clear all documents and embeddings."""
        self.documents = []
        self.embeddings = None
        logger.info("Vector store cleared")

    def get_stats(self) -> dict:
        """Get statistics about the vector store.

        Returns:
            Dictionary with stats
        """
        return {
            "total_documents": len(self.documents),
            "embedding_dimension": self.embeddings.shape[1] if self.embeddings is not None else 0,
            "model_name": self.model_name
        }
