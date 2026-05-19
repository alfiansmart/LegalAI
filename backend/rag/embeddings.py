"""Embedding model wrapper. Lazy-loaded to avoid heavy import at boot."""
from __future__ import annotations

from functools import lru_cache

from backend.config import get_settings


@lru_cache
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(get_settings().embedding_model)


def embed(texts: list[str], is_query: bool = False) -> list[list[float]]:
    # e5-style: prefix "query: " or "passage: "
    prefix = "query: " if is_query else "passage: "
    payload = [prefix + t for t in texts]
    out = _model().encode(payload, normalize_embeddings=True, show_progress_bar=False)
    return out.tolist()


def embed_one(text: str, is_query: bool = False) -> list[float]:
    return embed([text], is_query=is_query)[0]
