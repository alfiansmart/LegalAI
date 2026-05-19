"""Skill tool implementation: pasal_lookup."""
from __future__ import annotations

import asyncio
from datetime import date


def execute(agent=None, args: dict | None = None) -> dict:
    from backend.rag.temporal import pasal_as_of

    args = args or {}
    as_of = date.fromisoformat(args["as_of"]) if args.get("as_of") else date.today()
    result = asyncio.run(
        pasal_as_of(
            peraturan_jenis=args["jenis"],
            peraturan_nomor=args.get("nomor"),
            peraturan_tahun=args.get("tahun"),
            pasal_nomor=args["pasal"],
            as_of=as_of,
        )
    )
    if not result:
        return {"status": "not_found"}
    return {"status": "ok", "pasal": result}
