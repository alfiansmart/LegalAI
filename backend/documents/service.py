"""Document service — versioned drafts (perjanjian / memo / opini) with redline diff."""
from __future__ import annotations

from backend.db import models
from backend.db.session import session_scope


async def create_draft(user_id: str | None, title: str, kind: str, content: str,
                       template_id: str | None = None) -> int:
    async with session_scope() as s:
        doc = models.Document(
            user_id=user_id,
            title=title,
            kind=models.DocumentKind(kind),
            template_id=template_id,
        )
        s.add(doc)
        await s.flush()
        s.add(models.DocumentVersion(document_id=doc.id, version=1, content=content))
        return doc.id


async def new_version(document_id: int, content: str, note: str | None = None) -> int:
    from sqlalchemy import func, select

    async with session_scope() as s:
        v = await s.scalar(
            select(func.max(models.DocumentVersion.version)).where(
                models.DocumentVersion.document_id == document_id
            )
        )
        next_v = (v or 0) + 1
        s.add(
            models.DocumentVersion(
                document_id=document_id, version=next_v, content=content, note=note
            )
        )
        return next_v
