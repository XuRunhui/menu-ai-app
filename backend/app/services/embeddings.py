"""Shared sentence-embedding helpers: one model instance per process, DB-cached vectors."""

from __future__ import annotations

import logging
import threading
from typing import Callable

import numpy as np

from app.services import cache_service

logger = logging.getLogger(__name__)

_models: dict[tuple, object] = {}
_models_lock = threading.Lock()


def get_model(model_name: str, loader: Callable[[str], object]):
    """Load a model once per (loader, name); later calls reuse the same instance."""
    key = (loader, model_name)
    with _models_lock:
        if key not in _models:
            logger.info("Loading embedding model: %s", model_name)
            _models[key] = loader(model_name)
        return _models[key]


def embedding_dimension(model) -> int:
    # sentence-transformers renamed this method in newer releases; support both.
    getter = getattr(model, "get_embedding_dimension", None) or model.get_sentence_embedding_dimension
    return int(getter())


def embed_texts(
    model, model_name: str, texts: list[str], batch_size: int = 64, use_cache: bool = True
) -> np.ndarray:
    """Return a (len(texts), dim) float32 array, encoding only texts missing from the cache.

    use_cache=False skips the embedding_cache table (e.g. for knowledge chunks, which store
    their vectors in the knowledge database instead).
    """
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)

    dimensions = embedding_dimension(model)
    unique = list(dict.fromkeys(texts))
    vectors = (cache_service.get_embeddings(model_name, dimensions, unique) or {}) if use_cache else {}

    missing = [text for text in unique if text not in vectors]
    if missing:
        encoded = np.asarray(
            model.encode(missing, batch_size=batch_size, show_progress_bar=False, convert_to_numpy=True),
            dtype=np.float32,
        )
        new_vectors = dict(zip(missing, encoded))
        if use_cache:
            cache_service.set_embeddings(model_name, dimensions, new_vectors)
        vectors.update(new_vectors)

    logger.info("Embeddings: %d texts, %d from cache, %d encoded", len(unique), len(unique) - len(missing), len(missing))
    return np.vstack([vectors[text] for text in texts]).astype(np.float32)
