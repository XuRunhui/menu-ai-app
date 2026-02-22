"""Unit tests for VectorStore."""

import os
import sys

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("sentence_transformers")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.recommendation import vector_store as vector_store_module  # noqa: E402


class _FakeModel:
    def __init__(self, model_name: str):
        self.model_name = model_name

    def encode(self, texts, show_progress_bar=False, convert_to_numpy=True):
        def to_vec(text: str) -> np.ndarray:
            text_lower = text.lower()
            return np.array(
                [
                    1.0 if "spicy" in text_lower else 0.0,
                    1.0 if "salad" in text_lower else 0.0,
                    1.0 if "ramen" in text_lower else 0.0,
                ],
                dtype=float
            )

        if isinstance(texts, list):
            vectors = [to_vec(text) for text in texts]
        else:
            vectors = [to_vec(texts)]
        return np.vstack(vectors)

    def get_sentence_embedding_dimension(self):
        return 3


def test_vector_store_add_and_search(monkeypatch):
    """Vector store adds documents and returns relevant search results."""
    monkeypatch.setattr(vector_store_module, "SentenceTransformer", _FakeModel)
    store = vector_store_module.VectorStore()

    documents = [
        {"text": "Spicy ramen noodles", "dish": "Ramen", "metadata": {"type": "menu_description"}},
        {"text": "Garden salad with vinaigrette", "dish": "Salad", "metadata": {"type": "menu_description"}},
    ]

    store.add_documents(documents)
    assert store.embeddings is not None
    assert store.embeddings.shape[0] == 2

    results = store.search("spicy noodles", top_k=1)
    assert results
    assert results[0]["dish"] == "Ramen"


def test_vector_store_filter_by_dish(monkeypatch):
    """Search respects dish filter."""
    monkeypatch.setattr(vector_store_module, "SentenceTransformer", _FakeModel)
    store = vector_store_module.VectorStore()

    documents = [
        {"text": "Spicy ramen noodles", "dish": "Ramen", "metadata": {"type": "menu_description"}},
        {"text": "Garden salad with vinaigrette", "dish": "Salad", "metadata": {"type": "menu_description"}},
    ]

    store.add_documents(documents)

    results = store.search("spicy noodles", top_k=2, filter_dish="Salad")
    assert results
    assert all(result["dish"] == "Salad" for result in results)
