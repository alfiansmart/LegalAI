"""Document service — versioned drafts (perjanjian / memo / opini)."""
from __future__ import annotations

from sqlalchemy import func, select

from backend.db import models
from backend.db.session import session_scope


async def create_draft(
    user_id: str | None,
    title: str,
    kind: str,
    content: str,
    template_id: str | None = None,
    matter_id: int | None = None,
    source_filename: str | None = None,
) -> int:
    async with session_scope() as s:
        doc = models.Document(
            user_id=user_id,
            title=title,
            kind=models.DocumentKind(kind),
            template_id=template_id,
            matter_id=matter_id,
            source_filename=source_filename,
        )
        s.add(doc)
        await s.flush()
        s.add(models.DocumentVersion(document_id=doc.id, version=1, content=content))
        return doc.id


async def new_version(document_id: int, content: str, note: str | None = None) -> int:
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


async def latest_content(document_id: int) -> str | None:
    async with session_scope() as s:
        row = (
            await s.execute(
                select(models.DocumentVersion.content)
                .where(models.DocumentVersion.document_id == document_id)
                .order_by(models.DocumentVersion.version.desc())
                .limit(1)
            )
        ).first()
    return row.content if row else None


async def get_document(document_id: int) -> dict | None:
    async with session_scope() as s:
        doc = await s.get(models.Document, document_id)
        if not doc:
            return None
        versions = (
            await s.execute(
                select(models.DocumentVersion)
                .where(models.DocumentVersion.document_id == document_id)
                .order_by(models.DocumentVersion.version)
            )
        ).scalars().all()
    return {
        "id": doc.id,
        "title": doc.title,
        "kind": doc.kind.value if hasattr(doc.kind, "value") else doc.kind,
        "template_id": doc.template_id,
        "matter_id": doc.matter_id,
        "source_filename": doc.source_filename,
        "versions": [
            {
                "version": v.version,
                "content": v.content,
                "note": v.note,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in versions
        ],
    }


async def list_documents(
    user_id: str | None = None,
    matter_id: int | None = None,
    limit: int = 50,
) -> list[dict]:
    async with session_scope() as s:
        q = select(models.Document).order_by(models.Document.id.desc()).limit(limit)
        if user_id:
            q = q.where(models.Document.user_id == user_id)
        if matter_id is not None:
            q = q.where(models.Document.matter_id == matter_id)
        rows = (await s.execute(q)).scalars().all()
    return [
        {
            "id": d.id,
            "title": d.title,
            "kind": d.kind.value if hasattr(d.kind, "value") else d.kind,
            "template_id": d.template_id,
            "matter_id": d.matter_id,
            "source_filename": d.source_filename,
        }
        for d in rows
    ]
