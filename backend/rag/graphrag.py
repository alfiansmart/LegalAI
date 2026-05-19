"""Graph RAG: k-hop expansion over the citation graph + concept graph.

Stage [4] of the retrieval stack. Two graphs:
  - CitationEdge (deterministic, built at ingest from text parsing)
  - ConceptNode/ConceptEdge (LLM-extracted, MS-GraphRAG-style)

We query Postgres with recursive CTEs to avoid an extra graph DB.
"""
from __future__ import annotations

from sqlalchemy import text

from backend.db.session import session_scope


async def expand_citations(seed_pasal_ids: list[int], hops: int = 2) -> list[int]:
    """Walk CitationEdge up to `hops` from each seed pasal. Returns
    unique pasal ids ordered by hop distance."""
    if not seed_pasal_ids:
        return []
    sql = text(
        """
        WITH RECURSIVE walk(pasal_id, hop) AS (
            SELECT unnest(CAST(:seeds AS int[])) AS pasal_id, 0
            UNION ALL
            SELECT e.dst_pasal_id, w.hop + 1
            FROM walk w
            JOIN citation_edge e ON e.src_pasal_id = w.pasal_id
            WHERE w.hop < :hops
        )
        SELECT DISTINCT ON (pasal_id) pasal_id, hop
        FROM walk
        ORDER BY pasal_id, hop
        """
    )
    async with session_scope() as s:
        rows = (await s.execute(sql, {"seeds": seed_pasal_ids, "hops": hops})).all()
    rows_sorted = sorted(rows, key=lambda r: r.hop)
    return [r.pasal_id for r in rows_sorted]


async def concept_community_summary(concept_label: str) -> str | None:
    """Stub for MS-GraphRAG-style community summaries.

    Populated by a Celery task at ingest time; returns the precomputed
    summary blob if any.
    """
    sql = text("SELECT summary FROM concept_node WHERE label = :label LIMIT 1")
    async with session_scope() as s:
        row = (await s.execute(sql, {"label": concept_label})).first()
    return row.summary if row else None
