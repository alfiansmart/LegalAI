"""Celery tasks: embedding generation, graph building, RAPTOR build."""
from __future__ import annotations

import asyncio

from backend.worker import celery_app


@celery_app.task(name="rag.embed_pending")
def embed_pending(limit: int = 1000) -> dict:
    from backend.rag.embed_runner import embed_pending as runner

    stats = asyncio.run(runner(limit=limit))
    return {"scanned": stats.scanned, "embedded": stats.embedded, "skipped": stats.skipped}


@celery_app.task(name="rag.build_citation_edges")
def build_citation_edges(peraturan_id: int) -> None:
    # Phase-2: parse pasal text → extract Pasal references → write CitationEdge rows.
    raise NotImplementedError


@celery_app.task(name="rag.build_raptor")
def build_raptor(peraturan_id: int) -> None:
    raise NotImplementedError
