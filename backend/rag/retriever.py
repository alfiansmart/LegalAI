"""Hybrid retriever: BM25 + dense + (when scoped to a matter) DocumentChunk + rerank.

Composition:
  1. Peraturan corpus retrieval (BM25 + dense over pasal table).
  2. If `matter_id` is provided, also run dense retrieval over the
     matter's DocumentChunk rows and merge by score.
  3. Definition auto-injection: for every retrieved chunk that uses
     a defined term from its source document, attach the definition.
  4. Cross-reference expansion: parse "Pasal X …" inside retrieved
     text and attach the referenced pasal (depth ≤ 1) via temporal.
  5. Rerank the merged candidate set with Haiku as a cross-encoder.

The return shape is a flat list of dicts, each tagged with
`source ∈ {pasal, document_chunk}`. The harness / task endpoints
consume this uniformly.
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
    """Hybrid retrieval entrypoint.

    Stages above retrieval (graph expansion, CRAG, agentic refinement)
    are composed by the agent harness, not by the retriever itself.
    """

    async def search(
        self,
        q: str,
        k: int = 10,
        jenis: list[str] | None = None,
        as_of: str | None = None,
        expand_graph: bool = True,
        matter_id: int | None = None,
        rerank: bool = True,
        rerank_top_k: int | None = None,
        include_raptor: bool = True,
    ) -> list[dict]:
        from backend.rag.embeddings import embed_one

        qvec = embed_one(q, is_query=True)
        as_of_date = date.fromisoformat(as_of) if as_of else date.today()

        # Pull a wider candidate set than `k` so the reranker has room
        # to actually re-rank. We chop down to k at the end.
        candidate_k = max(k * 3, 20) if rerank else k

        hits: list[dict] = await self._pasal_search(q, qvec, candidate_k, jenis, as_of_date)

        if matter_id is not None:
            chunk_hits = await self._document_chunk_search(q, qvec, candidate_k, matter_id)
            hits.extend(chunk_hits)

        # RAPTOR — mix in branch summaries so broad/aggregate queries get
        # the right Bab / document-level node alongside leaf pasal.
        if include_raptor:
            branch_hits = await self._raptor_branch_search(qvec, k=min(5, candidate_k))
            hits.extend(branch_hits)

        # Expansion stages — only on the candidate set, before rerank.
        await self._inject_definitions(hits)
        await self._expand_cross_references(hits, as_of_date)

        if rerank and len(hits) > k:
            from backend.rag.reranker import rerank as rerank_fn

            hits = await rerank_fn(q, hits, top_k=rerank_top_k or k)
        else:
            hits = hits[:k]
        return hits

    # ------------------------------------------------------------------
    # Stage 1: pasal table (BM25 + dense)
    # ------------------------------------------------------------------

    async def _pasal_search(
        self,
        q: str,
        qvec: list[float],
        k: int,
        jenis: list[str] | None,
        as_of_date: date,
    ) -> list[dict]:
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
                   p.hierarchy_level,
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

        from backend.legal.hierarchy import hierarchy_boost

        hits: list[dict] = []
        for r in rows:
            label = _peraturan_label(r.jenis, r.p_nomor, r.tahun)
            base_score = float(r.score)
            level = r.hierarchy_level
            boost = hierarchy_boost(level)
            hits.append(
                {
                    "source": "pasal",
                    "pasal_id": r.id,
                    "peraturan": label,
                    "pasal": r.pasal_nomor,
                    "ayat": None,
                    "huruf": None,
                    "hierarchy_level": level,
                    "score": base_score + boost,
                    "_base_score": base_score,
                    "_hierarchy_boost": boost,
                    "snippet": (r.teks or "")[:300],
                    "teks": r.teks or "",
                }
            )
        # Re-sort after the boost so two equally-relevant rows go to the
        # higher-authority one (lex superior).
        hits.sort(key=lambda h: h["score"], reverse=True)
        return hits

    # ------------------------------------------------------------------
    # Stage 2: DocumentChunk dense search scoped to a matter
    # ------------------------------------------------------------------

    async def _document_chunk_search(
        self,
        q: str,
        qvec: list[float],
        k: int,
        matter_id: int,
    ) -> list[dict]:
        sql = text(
            """
            SELECT
                dc.id AS chunk_id,
                dc.document_id,
                dc.text,
                dc.contextual_text,
                dc.breadcrumb,
                dc.parent_summary,
                d.title,
                1 - (dc.embedding <=> CAST(:qvec AS vector)) AS score
            FROM document_chunk dc
            JOIN document d ON d.id = dc.document_id
            WHERE dc.matter_id = :matter_id
              AND dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> CAST(:qvec AS vector)
            LIMIT :k
            """
        )
        async with session_scope() as s:
            rows = (await s.execute(sql, {"qvec": qvec, "matter_id": matter_id, "k": k})).all()
        hits: list[dict] = []
        for r in rows:
            hits.append(
                {
                    "source": "document_chunk",
                    "chunk_id": r.chunk_id,
                    "document_id": r.document_id,
                    "document_title": r.title,
                    "breadcrumb": r.breadcrumb,
                    "parent_summary": r.parent_summary,
                    "score": float(r.score),
                    "snippet": (r.text or "")[:300],
                    "text": r.text or "",
                    "contextual_text": r.contextual_text or r.text or "",
                }
            )
        return hits

    # ------------------------------------------------------------------
    # RAPTOR branch mix-in
    # ------------------------------------------------------------------

    async def _raptor_branch_search(self, qvec: list[float], k: int = 5) -> list[dict]:
        from backend.rag.raptor import search_branches

        try:
            rows = await search_branches(qvec, k=k, level_min=1)
        except Exception:  # noqa: BLE001 — raptor_node may not exist yet in early dev
            return []
        out: list[dict] = []
        for r in rows:
            out.append(
                {
                    "source": "raptor",
                    "raptor_id": r["id"],
                    "raptor_level": r["level"],
                    "title": r["title"],
                    "score": r["score"],
                    "snippet": (r["summary"] or "")[:300],
                    "summary": r["summary"] or "",
                }
            )
        return out

    # ------------------------------------------------------------------
    # Stage 3: defined-terms injection
    # ------------------------------------------------------------------

    async def _inject_definitions(self, hits: list[dict]) -> None:
        """For each chunk hit, attach defs of any defined terms it uses."""
        from sqlalchemy import select

        from backend.db import models
        from backend.rag.definitions import find_terms_in_text

        doc_ids = {h["document_id"] for h in hits if h["source"] == "document_chunk"}
        if not doc_ids:
            return
        async with session_scope() as s:
            rows = (
                (
                    await s.execute(
                        select(models.DocumentTerm).where(
                            models.DocumentTerm.document_id.in_(doc_ids)
                        )
                    )
                )
                .scalars()
                .all()
            )
        terms_by_doc: dict[int, dict[str, str]] = {}
        for t in rows:
            terms_by_doc.setdefault(t.document_id, {})[t.term] = t.definition
        for h in hits:
            if h.get("source") != "document_chunk":
                continue
            terms_map = terms_by_doc.get(h["document_id"])
            if not terms_map:
                continue
            used = find_terms_in_text(h.get("text", ""), list(terms_map.keys()))
            if used:
                h["definitions"] = {t: terms_map[t] for t in used}

    # ------------------------------------------------------------------
    # Stage 4: cross-reference expansion (Pasal X → resolved pasal row)
    # ------------------------------------------------------------------

    async def _expand_cross_references(self, hits: list[dict], as_of: date) -> None:
        from backend.rag.citation import parse_citations
        from backend.rag.temporal import pasal_as_of

        for h in hits:
            blob = h.get("teks") or h.get("text") or ""
            if not blob:
                continue
            refs = parse_citations(blob)
            resolved: list[dict] = []
            seen: set[tuple] = set()
            for ref in refs:
                if not ref.jenis or not ref.pasal:
                    continue
                key = (ref.jenis, ref.nomor, ref.tahun, ref.pasal, ref.ayat, ref.huruf)
                if key in seen:
                    continue
                seen.add(key)
                r = await pasal_as_of(
                    peraturan_jenis=ref.jenis,
                    peraturan_nomor=ref.nomor,
                    peraturan_tahun=ref.tahun,
                    pasal_nomor=ref.pasal,
                    ayat_nomor=ref.ayat,
                    huruf=ref.huruf,
                    as_of=as_of,
                )
                if r and r.get("id") and r.get("id") != h.get("pasal_id"):
                    resolved.append(
                        {
                            "pasal_id": r["id"],
                            "label": r.get("peraturan", {}).get("label", ref.jenis),
                            "pasal": r.get("nomor"),
                            "snippet": (r.get("teks") or "")[:200],
                        }
                    )
            if resolved:
                h["cross_references"] = resolved


def _peraturan_label(jenis: str, nomor: str | None, tahun: int | None) -> str:
    if jenis in {"KUHP", "KUHPerdata", "KUHAP", "UUD"}:
        return jenis
    return f"{jenis} {nomor}/{tahun}" if nomor else jenis
