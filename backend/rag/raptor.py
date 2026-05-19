"""RAPTOR-style hierarchical summary tree.

Built by a Celery task at ingest time. At retrieval, the harness mixes
leaf hits (precise pasal text) with branch summaries (Bab / Topic) so
broad queries get both detail and context.
"""
from __future__ import annotations

from sqlalchemy import text

from backend.db.session import session_scope


async def search_branches(qvec: list[float], k: int = 5, level_min: int = 1) -> list[dict]:
    sql = text(
        """
        SELECT id, level, title, summary,
               1 - (embedding <=> CAST(:qvec AS vector)) AS score
        FROM raptor_node
        WHERE embedding IS NOT NULL AND level >= :level_min
        ORDER BY embedding <=> CAST(:qvec AS vector)
        LIMIT :k
        """
    )
    async with session_scope() as s:
        rows = (await s.execute(sql, {"qvec": qvec, "k": k, "level_min": level_min})).all()
    return [
        {"id": r.id, "level": r.level, "title": r.title, "summary": r.summary, "score": float(r.score)}
        for r in rows
    ]
