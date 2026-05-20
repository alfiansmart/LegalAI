"""Agentic retrieval orchestrator.

Chains the Phase 5 retrieval improvements into one entrypoint the
harness can invoke as a tool:

  1. Decompose the question into ≤4 sub-queries.
  2. For each sub-query, run HyDE → retrieve via HybridRetriever.
  3. Merge candidates, de-dup, rerank.
  4. CRAG-grade the merged evidence.
  5. If verdict is INSUFFICIENT and we haven't retried, rewrite with
     the grader's `refined_query` and run one more retrieval pass.

Returns the merged top-k hits plus a `trace` of what happened so the
agent can decide whether to keep going or surface a "need more info"
reply to the user.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from backend.rag.crag import Grade, Verdict, grade as crag_grade
from backend.rag.decomposition import decompose
from backend.rag.hyde import hypothetical_answer
from backend.rag.retriever import HybridRetriever

_log = logging.getLogger(__name__)


@dataclass(slots=True)
class AgenticHit:
    hit: dict
    via_subquery: str
    score: float


@dataclass(slots=True)
class AgenticResult:
    hits: list[dict]
    subqueries: list[str]
    grade: Grade
    retried: bool = False
    trace: list[dict] = field(default_factory=list)


async def agentic_search(
    question: str,
    *,
    matter_id: int | None = None,
    k: int = 10,
    as_of: str | None = None,
    use_hyde: bool = True,
    use_decomposition: bool = True,
    use_crag: bool = True,
) -> AgenticResult:
    retriever = HybridRetriever()
    trace: list[dict] = []

    # ---- 1) decompose
    subqueries = await decompose(question) if use_decomposition else [question]
    trace.append({"event": "decompose", "n": len(subqueries), "subqueries": subqueries})

    # ---- 2) for each sub-query, HyDE → retrieve. Merge by pasal_id/chunk_id.
    merged: dict[str, dict] = {}
    for sq in subqueries:
        query_text = await hypothetical_answer(sq) if use_hyde else sq
        trace.append(
            {
                "event": "subquery",
                "q": sq,
                "hyde_used": use_hyde and query_text != sq,
                "embed_source_preview": query_text[:120],
            }
        )
        sub_hits = await retriever.search(
            query_text,
            k=max(k, 8),
            as_of=as_of,
            matter_id=matter_id,
            rerank=False,  # we rerank once at the end over the merged set
        )
        for h in sub_hits:
            key = _key(h)
            existing = merged.get(key)
            score = float(h.get("score", 0.0))
            if not existing or score > float(existing.get("score", 0.0)):
                h["_via_subquery"] = sq
                merged[key] = h

    candidates = list(merged.values())
    trace.append({"event": "merge", "candidates": len(candidates)})

    # ---- 3) rerank the merged set against the *original* question.
    if len(candidates) > k:
        from backend.rag.reranker import rerank as rerank_fn
        candidates = await rerank_fn(question, candidates, top_k=k)
    else:
        candidates.sort(key=lambda h: float(h.get("score", 0.0)), reverse=True)
        candidates = candidates[:k]

    # ---- 4) CRAG grade
    if use_crag:
        g = await crag_grade(question, candidates)
    else:
        g = Grade(Verdict.SUFFICIENT, "crag disabled")
    trace.append({"event": "grade", "verdict": g.verdict.value, "reason": g.reason})

    # ---- 5) one retry if insufficient
    retried = False
    if use_crag and g.verdict == Verdict.INSUFFICIENT and g.refined_query and g.refined_query != question:
        retried = True
        trace.append({"event": "retry", "refined_query": g.refined_query})
        query_text = await hypothetical_answer(g.refined_query) if use_hyde else g.refined_query
        retry_hits = await retriever.search(
            query_text, k=k * 2, as_of=as_of, matter_id=matter_id, rerank=False
        )
        for h in retry_hits:
            key = _key(h)
            if key not in merged:
                h["_via_subquery"] = g.refined_query
                merged[key] = h
        candidates = list(merged.values())
        if len(candidates) > k:
            from backend.rag.reranker import rerank as rerank_fn
            candidates = await rerank_fn(question, candidates, top_k=k)
        else:
            candidates.sort(key=lambda h: float(h.get("score", 0.0)), reverse=True)
            candidates = candidates[:k]
        g = await crag_grade(question, candidates)
        trace.append({"event": "regrade", "verdict": g.verdict.value, "reason": g.reason})

    return AgenticResult(
        hits=candidates, subqueries=subqueries, grade=g, retried=retried, trace=trace
    )


def _key(h: dict) -> str:
    if h.get("source") == "document_chunk":
        return f"chunk:{h.get('chunk_id')}"
    return f"pasal:{h.get('pasal_id')}"
