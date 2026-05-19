"""Skill tool implementation: peraturan_search."""
from __future__ import annotations

import asyncio


def execute(agent=None, args: dict | None = None) -> dict:
    from backend.rag.retriever import HybridRetriever

    args = args or {}
    retriever = HybridRetriever()
    hits = asyncio.run(
        retriever.search(
            q=args["q"],
            k=int(args.get("k", 10)),
            jenis=args.get("jenis"),
            as_of=args.get("as_of"),
            expand_graph=bool(args.get("expand_graph", True)),
        )
    )
    return {"status": "ok", "hits": hits}
