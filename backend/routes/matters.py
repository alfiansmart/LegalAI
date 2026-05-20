"""Matter (case/engagement) CRUD + nested document listing.

Matters are the primary workspace organizing unit. Every chat session
and document can belong to a matter; the agent reads `matter.notes_md`
on each turn (analogous to CLAUDE.md for Claude Code projects).
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.db import models
from backend.db.session import session_scope

router = APIRouter()


class MatterIn(BaseModel):
    name: str
    client: str | None = None
    description: str | None = None
    notes_md: str | None = None


class MatterPatch(BaseModel):
    name: str | None = None
    client: str | None = None
    description: str | None = None
    notes_md: str | None = None
    status: str | None = Field(default=None, description="active|archived|closed")


class MatterOut(BaseModel):
    id: int
    slug: str
    name: str
    client: str | None
    description: str | None
    notes_md: str | None
    status: str
    created_at: datetime | None
    updated_at: datetime | None


def _to_out(m: models.Matter) -> MatterOut:
    return MatterOut(
        id=m.id,
        slug=m.slug,
        name=m.name,
        client=m.client,
        description=m.description,
        notes_md=m.notes_md,
        status=m.status.value if hasattr(m.status, "value") else m.status,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


@router.get("", response_model=list[MatterOut])
async def list_matters(status: str | None = None) -> list[MatterOut]:
    async with session_scope() as s:
        q = select(models.Matter).order_by(models.Matter.updated_at.desc())
        if status:
            q = q.where(models.Matter.status == models.MatterStatus(status))
        rows = (await s.execute(q)).scalars().all()
    return [_to_out(m) for m in rows]


@router.post("", response_model=MatterOut)
async def create_matter(req: MatterIn) -> MatterOut:
    slug = _slugify(req.name)
    async with session_scope() as s:
        # Ensure unique slug.
        existing = (
            await s.execute(select(models.Matter).where(models.Matter.slug.like(f"{slug}%")))
        ).scalars().all()
        if existing:
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"
        m = models.Matter(
            slug=slug,
            name=req.name,
            client=req.client,
            description=req.description,
            notes_md=req.notes_md or _default_notes_md(req),
        )
        s.add(m)
        await s.flush()
        return _to_out(m)


@router.get("/{matter_id}", response_model=MatterOut)
async def get_matter(matter_id: int) -> MatterOut:
    async with session_scope() as s:
        m = await s.get(models.Matter, matter_id)
        if not m:
            raise HTTPException(404, "matter not found")
        return _to_out(m)


@router.patch("/{matter_id}", response_model=MatterOut)
async def update_matter(matter_id: int, req: MatterPatch) -> MatterOut:
    async with session_scope() as s:
        m = await s.get(models.Matter, matter_id)
        if not m:
            raise HTTPException(404, "matter not found")
        if req.name is not None:
            m.name = req.name
        if req.client is not None:
            m.client = req.client
        if req.description is not None:
            m.description = req.description
        if req.notes_md is not None:
            m.notes_md = req.notes_md
        if req.status is not None:
            m.status = models.MatterStatus(req.status)
        return _to_out(m)


@router.get("/{matter_id}/documents")
async def matter_documents(matter_id: int) -> list[dict]:
    async with session_scope() as s:
        rows = (
            await s.execute(
                select(models.Document)
                .where(models.Document.matter_id == matter_id)
                .order_by(models.Document.id.desc())
            )
        ).scalars().all()
    return [
        {
            "id": d.id,
            "title": d.title,
            "kind": d.kind.value if hasattr(d.kind, "value") else d.kind,
            "template_id": d.template_id,
            "source_filename": d.source_filename,
        }
        for d in rows
    ]


@router.get("/{matter_id}/activity")
async def matter_activity(matter_id: int, limit: int = 20) -> list[dict]:
    """Recent chat turns + document creations in this matter."""
    async with session_scope() as s:
        turns = (
            await s.execute(
                select(models.Turn)
                .join(models.Session, models.Session.id == models.Turn.session_id)
                .where(models.Session.matter_id == matter_id)
                .order_by(models.Turn.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
        docs = (
            await s.execute(
                select(models.Document)
                .where(models.Document.matter_id == matter_id)
                .order_by(models.Document.created_at.desc())
                .limit(10)
            )
        ).scalars().all()
    events = [
        {
            "kind": "turn",
            "role": t.role,
            "text": (t.content or "")[:200],
            "at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in turns
    ] + [
        {
            "kind": "document",
            "title": d.title,
            "doc_kind": d.kind.value if hasattr(d.kind, "value") else d.kind,
            "at": d.created_at.isoformat() if d.created_at else None,
            "document_id": d.id,
        }
        for d in docs
    ]
    events.sort(key=lambda e: e.get("at") or "", reverse=True)
    return events[:limit]


# ----------------------------------------------------------------------


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(s: str) -> str:
    return _SLUG_RE.sub("-", s.lower()).strip("-")[:64] or "matter"


def _default_notes_md(req: MatterIn) -> str:
    parts = [f"# {req.name}", ""]
    if req.client:
        parts.append(f"**Klien**: {req.client}")
    if req.description:
        parts.append(f"**Ringkasan**: {req.description}")
    parts.extend(
        [
            "",
            "## Konteks",
            "<!-- Tulis fakta-fakta kunci, instruksi klien, dan info yang harus diingat agent. -->",
            "",
            "## Tujuan",
            "<!-- Outcome yang diharapkan. -->",
            "",
            "## Tenggat & Tanggal Penting",
            "- ",
        ]
    )
    return "\n".join(parts)
