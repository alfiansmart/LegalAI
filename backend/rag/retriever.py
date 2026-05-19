"""Hybrid retriever: BM25 (tsvector) + dense (pgvector) + structured + graph expansion.

This is the canonical entrypoint. Layered stages are implemented in
sibling modules (`graphrag.py`, `raptor.py`, `colbert_index.py`, `crag.py`,
`temporal.py`) and composed here per the architecture in the plan.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import text

from backend.db.session import session_scope


@dataclass(slots=True)
class Hit:
    pasal_id: int
    peraturan: str
    pasal: str
    ayat: str | None
    huruf: str | None
    score: float
    snippet: str


class HybridRetriever:
    """Stage [3] hybrid retrieval — BM25 + dense.

    Stages [4]-[6] (graph expansion, rerank, CRAG) are composed by the
    agent harness, not by the retriever itself.
    """

    async def search(
        self,
        q: str,
        k: int = 10,
        jenis: list[str] | None = None,
        as_of: str | None = None,
        expand_graph: bool = True,
    ) -> list[dict]:
        from backend.rag.embeddings import embed_one

        qvec = embed_one(q, is_query=True)
        as_of_date = date.fromisoformat(as_of) if as_of else date.today()
        jenis_clause = ""
        params: dict = {"q": q, "qvec": qvec, "k": k, "as_of": as_of_date}
        if jenis:
            jenis_clause = "AND p.jenis = ANY(:jenis)"
            params["jenis"] = jenis

        sql = text(
            f"""
            WITH bm25 AS (
                SELECT pasal.id AS pasal_id,
                       ts_rank(to_tsvector('simple', pasal.teks),
                               plainto_tsquery('simple', :q)) AS score
                FROM pasal
                JOIN peraturan p ON p.id = pasal.peraturan_id
                WHERE to_tsvector('simple', pasal.teks) @@ plainto_tsquery('simple', :q)
                  AND (pasal.effective_from IS NULL OR pasal.effective_from <= :as_of)
                  AND (pasal.effective_to   IS NULL OR pasal.effective_to   >= :as_of)
                  {jenis_clause}
                ORDER BY score DESC
                LIMIT :k
            ),
            dense AS (
                SELECT pasal.id AS pasal_id,
                       1 - (pasal.embedding <=> CAST(:qvec AS vector)) AS score
                FROM pasal
                JOIN peraturan p ON p.id = pasal.peraturan_id
                WHERE pasal.embedding IS NOT NULL
                  AND (pasal.effective_from IS NULL OR pasal.effective_from <= :as_of)
                  AND (pasal.effective_to   IS NULL OR pasal.effective_to   >= :as_of)
                  {jenis_clause}
                ORDER BY pasal.embedding <=> CAST(:qvec AS vector)
                LIMIT :k
            ),
            merged AS (
                SELECT pasal_id, MAX(score) AS score FROM (
                    SELECT pasal_id, score FROM bm25
                    UNION ALL
                    SELECT pasal_id, score FROM dense
                ) u
                GROUP BY pasal_id
            )
            SELECT pasal.id, pasal.nomor AS pasal_nomor, pasal.teks,
                   p.jenis, p.nomor AS p_nomor, p.tahun, p.judul,
                   merged.score
            FROM merged
            JOIN pasal ON pasal.id = merged.pasal_id
            JOIN peraturan p ON p.id = pasal.peraturan_id
            ORDER BY merged.score DESC
            LIMIT :k
            """
        )

        async with session_scope() as s:
            rows = (await s.execute(sql, params)).all()

        hits: list[dict] = []
        for r in rows:
            label = _peraturan_label(r.jenis, r.p_nomor, r.tahun)
            hits.append(
                {
                    "pasal_id": r.id,
                    "peraturan": label,
                    "pasal": r.pasal_nomor,
                    "ayat": None,
                    "huruf": None,
                    "score": float(r.score),
                    "snippet": (r.teks or "")[:300],
                }
            )
        return hits


def _peraturan_label(jenis: str, nomor: str | None, tahun: int | None) -> str:
    if jenis in {"KUHP", "KUHPerdata", "KUHAP", "UUD"}:
        return jenis
    return f"{jenis} {nomor}/{tahun}" if nomor else jenis
