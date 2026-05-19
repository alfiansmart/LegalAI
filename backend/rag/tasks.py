"""Celery tasks: embedding generation, graph building, RAPTOR build."""
from __future__ import annotations

from backend.worker import celery_app


@celery_app.task(name="rag.embed_pasal")
def embed_pasal(pasal_id: int) -> None:
    # Implementation lands in Phase 1 — embeds pasal.teks (+ ayat/huruf)
    # and writes back to pasal.embedding via session_scope.
    raise NotImplementedError


@celery_app.task(name="rag.build_citation_edges")
def build_citation_edges(peraturan_id: int) -> None:
    raise NotImplementedError


@celery_app.task(name="rag.build_raptor")
def build_raptor(peraturan_id: int) -> None:
    raise NotImplementedError
