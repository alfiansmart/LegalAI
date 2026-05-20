"""Agentic search tool — wraps the agentic retrieval orchestrator and
returns a structured payload + an optional citation-trace artifact."""
from __future__ import annotations


async def execute(agent=None, args: dict | None = None) -> dict:
    from backend.agents import artifacts as A
    from backend.rag.agentic import agentic_search

    args = args or {}
    question = args.get("question")
    if not question:
        return {"status": "error", "message": "need question"}

    matter_id = args.get("matter_id")
    if matter_id is not None:
        try:
            matter_id = int(matter_id)
        except (TypeError, ValueError):
            matter_id = None

    result = await agentic_search(
        question=str(question),
        matter_id=matter_id,
        k=int(args.get("k", 10)),
        as_of=args.get("as_of"),
    )

    artifacts: list[dict] = []
    if len(result.subqueries) > 1:
        rows = [[i + 1, sq] for i, sq in enumerate(result.subqueries)]
        artifacts.append(A.table("Dekomposisi kueri", ["#", "Sub-pertanyaan"], rows))

    return {
        "status": "ok",
        "hits": result.hits,
        "subqueries": result.subqueries,
        "verdict": result.grade.verdict.value,
        "verdict_reason": result.grade.reason,
        "retried": result.retried,
        "trace": result.trace,
        "artifacts": artifacts,
    }
