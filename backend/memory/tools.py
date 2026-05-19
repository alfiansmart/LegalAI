"""Agent-callable wrappers for the memory layer (used by the harness if
the persona's allowed-skill list includes a `memory` skill — Phase 2)."""
from __future__ import annotations

from backend.memory import semantic


async def recall(agent=None, args: dict | None = None) -> dict:
    args = args or {}
    user_id = (args.get("user_id") or "anonymous")
    items = await semantic.recall(user_id, args["q"], k=int(args.get("k", 5)))
    return {"status": "ok", "items": items}


async def add(agent=None, args: dict | None = None) -> dict:
    args = args or {}
    user_id = (args.get("user_id") or "anonymous")
    mid = await semantic.add(user_id, args["content"], kind=args.get("kind", "fact"))
    return {"status": "ok", "id": mid}
