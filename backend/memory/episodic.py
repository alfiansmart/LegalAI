"""Episodic memory — per-session turn history."""
from __future__ import annotations

from sqlalchemy import select

from backend.db import models
from backend.db.session import session_scope


async def recent(session_id: str, limit: int = 20) -> list[dict]:
    async with session_scope() as s:
        rows = (
            await s.execute(
                select(models.Turn)
                .where(models.Turn.session_id == session_id)
                .order_by(models.Turn.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
    return [
        {"role": t.role, "content": t.content, "tool": t.tool_name} for t in reversed(rows)
    ]
