from __future__ import annotations

import asyncio


def execute(agent=None, args: dict | None = None) -> dict:
    from backend.rag.graphrag import expand_citations

    args = args or {}
    pasal_ids = asyncio.run(expand_citations([int(args["pasal_id"])], hops=int(args.get("hops", 2))))
    return {"status": "ok", "pasal_ids": pasal_ids}
