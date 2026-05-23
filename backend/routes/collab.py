"""Collaboration endpoints: matter membership, comments, suggestions, audit log.

All endpoints respect the role ladder declared in auth.identity:
  viewer < reviewer < editor < owner
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from backend.auth import audit, identity
from backend.db import models
from backend.db.session import session_scope

router = APIRouter()


# ---------------------------------------------------------------------------
# Matter membership
# ---------------------------------------------------------------------------


class MatterMemberIn(BaseModel):
    user_id: str
    role: str = "editor"  # owner|editor|reviewer|viewer


class MatterMemberOut(BaseModel):
    id: int
    matter_id: int
    user_id: str
    role: str
    user_name: str | None = None
    user_email: str | None = None


@router.get("/matters/{matter_id}/members", response_model=list[MatterMemberOut])
async def list_members(
    matter_id: int,
    ident: identity.Identity = Depends(identity.current_user),
) -> list[MatterMemberOut]:
    await identity.require_matter_access(matter_id, ident, minimum="viewer")
    async with session_scope() as s:
        rows = (
            await s.execute(
                select(models.MatterMember, models.User)
                .outerjoin(models.User, models.User.id == models.MatterMember.user_id)
                .where(models.MatterMember.matter_id == matter_id)
            )
        ).all()
    out: list[MatterMemberOut] = []
    for m, u in rows:
        out.append(
            MatterMemberOut(
                id=m.id,
                matter_id=m.matter_id,
                user_id=m.user_id,
                role=m.role.value if hasattr(m.role, "value") else str(m.role),
                user_name=u.name if u else None,
                user_email=u.email if u else None,
            )
        )
    return out


@router.post("/matters/{matter_id}/members", response_model=MatterMemberOut)
async def add_member(
    matter_id: int,
    body: MatterMemberIn,
    ident: identity.Identity = Depends(identity.current_user),
) -> MatterMemberOut:
    await identity.require_matter_access(matter_id, ident, minimum="owner")
    try:
        role = models.MatterMemberRole(body.role)
    except ValueError:
        raise HTTPException(400, f"unknown role {body.role!r}")
    async with session_scope() as s:
        m = models.MatterMember(matter_id=matter_id, user_id=body.user_id, role=role)
        s.add(m)
        try:
            await s.flush()
        except Exception:
            await s.rollback()
            raise HTTPException(409, "user already a member")
        member_id = m.id

    await audit.record(
        action="matter.member_add",
        user_id=ident.user_id,
        object_kind="matter",
        object_id=matter_id,
        payload={"user_id": body.user_id, "role": body.role},
    )
    return MatterMemberOut(
        id=member_id,
        matter_id=matter_id,
        user_id=body.user_id,
        role=body.role,
    )


@router.delete("/matters/{matter_id}/members/{user_id}")
async def remove_member(
    matter_id: int,
    user_id: str,
    ident: identity.Identity = Depends(identity.current_user),
) -> dict:
    await identity.require_matter_access(matter_id, ident, minimum="owner")
    async with session_scope() as s:
        m = (
            await s.execute(
                select(models.MatterMember).where(
                    models.MatterMember.matter_id == matter_id,
                    models.MatterMember.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if m is None:
            raise HTTPException(404, "membership not found")
        await s.delete(m)

    await audit.record(
        action="matter.member_remove",
        user_id=ident.user_id,
        object_kind="matter",
        object_id=matter_id,
        payload={"user_id": user_id},
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


class CommentIn(BaseModel):
    body: str
    range_start: int | None = None
    range_end: int | None = None
    parent_id: int | None = None


class CommentOut(BaseModel):
    id: int
    document_id: int
    user_id: str | None
    user_name: str | None = None
    parent_id: int | None
    range_start: int | None
    range_end: int | None
    body: str
    resolved: bool
    created_at: str


@router.get("/documents/{document_id}/comments", response_model=list[CommentOut])
async def list_comments(
    document_id: int,
    ident: identity.Identity = Depends(identity.current_user),
) -> list[CommentOut]:
    matter_id = await _matter_id_for_document(document_id)
    if matter_id is not None:
        await identity.require_matter_access(matter_id, ident, minimum="viewer")
    async with session_scope() as s:
        rows = (
            await s.execute(
                select(models.Comment, models.User)
                .outerjoin(models.User, models.User.id == models.Comment.user_id)
                .where(models.Comment.document_id == document_id)
                .order_by(models.Comment.created_at)
            )
        ).all()
    return [
        CommentOut(
            id=c.id,
            document_id=c.document_id,
            user_id=c.user_id,
            user_name=u.name if u else None,
            parent_id=c.parent_id,
            range_start=c.range_start,
            range_end=c.range_end,
            body=c.body,
            resolved=c.resolved,
            created_at=c.created_at.isoformat() if c.created_at else "",
        )
        for c, u in rows
    ]


@router.post("/documents/{document_id}/comments", response_model=CommentOut)
async def add_comment(
    document_id: int,
    body: CommentIn,
    ident: identity.Identity = Depends(identity.current_user),
) -> CommentOut:
    matter_id = await _matter_id_for_document(document_id)
    if matter_id is not None:
        await identity.require_matter_access(matter_id, ident, minimum="reviewer")
    if not body.body.strip():
        raise HTTPException(400, "empty body")

    async with session_scope() as s:
        # Verify document exists.
        if await s.get(models.Document, document_id) is None:
            raise HTTPException(404, "document not found")
        c = models.Comment(
            document_id=document_id,
            user_id=ident.user_id if ident.is_authenticated else None,
            parent_id=body.parent_id,
            range_start=body.range_start,
            range_end=body.range_end,
            body=body.body.strip(),
        )
        s.add(c)
        await s.flush()
        new_id = c.id
        created_at = c.created_at

    await audit.record(
        action="comment.add",
        user_id=ident.user_id,
        object_kind="comment",
        object_id=new_id,
        payload={"document_id": document_id, "parent_id": body.parent_id},
    )
    return CommentOut(
        id=new_id,
        document_id=document_id,
        user_id=ident.user_id if ident.is_authenticated else None,
        user_name=ident.name,
        parent_id=body.parent_id,
        range_start=body.range_start,
        range_end=body.range_end,
        body=body.body.strip(),
        resolved=False,
        created_at=created_at.isoformat() if created_at else "",
    )


@router.post("/comments/{comment_id}/resolve")
async def resolve_comment(
    comment_id: int,
    ident: identity.Identity = Depends(identity.current_user),
) -> dict:
    async with session_scope() as s:
        c = await s.get(models.Comment, comment_id)
        if c is None:
            raise HTTPException(404, "comment not found")
        matter_id = await _matter_id_for_document(c.document_id)
        if matter_id is not None:
            await identity.require_matter_access(matter_id, ident, minimum="reviewer")
        c.resolved = True
    await audit.record(
        action="comment.resolve",
        user_id=ident.user_id,
        object_kind="comment",
        object_id=comment_id,
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Suggestions (track-changes)
# ---------------------------------------------------------------------------


class SuggestionIn(BaseModel):
    range_start: int
    range_end: int
    base_text: str
    proposed_text: str
    rationale: str | None = None
    source: str = "human"  # ai|human


class SuggestionOut(BaseModel):
    id: int
    document_id: int
    user_id: str | None
    source: str
    range_start: int
    range_end: int
    base_text: str
    proposed_text: str
    rationale: str | None
    status: str
    created_at: str


@router.get("/documents/{document_id}/suggestions", response_model=list[SuggestionOut])
async def list_suggestions(
    document_id: int,
    ident: identity.Identity = Depends(identity.current_user),
) -> list[SuggestionOut]:
    matter_id = await _matter_id_for_document(document_id)
    if matter_id is not None:
        await identity.require_matter_access(matter_id, ident, minimum="viewer")
    async with session_scope() as s:
        rows = (
            (
                await s.execute(
                    select(models.Suggestion)
                    .where(models.Suggestion.document_id == document_id)
                    .order_by(models.Suggestion.created_at)
                )
            )
            .scalars()
            .all()
        )
    return [_to_suggestion_out(r) for r in rows]


@router.post("/documents/{document_id}/suggestions", response_model=SuggestionOut)
async def add_suggestion(
    document_id: int,
    body: SuggestionIn,
    ident: identity.Identity = Depends(identity.current_user),
) -> SuggestionOut:
    matter_id = await _matter_id_for_document(document_id)
    if matter_id is not None:
        await identity.require_matter_access(matter_id, ident, minimum="reviewer")
    if body.range_end < body.range_start:
        raise HTTPException(400, "range_end must be ≥ range_start")
    async with session_scope() as s:
        if await s.get(models.Document, document_id) is None:
            raise HTTPException(404, "document not found")
        sug = models.Suggestion(
            document_id=document_id,
            user_id=ident.user_id if ident.is_authenticated else None,
            source=body.source,
            range_start=body.range_start,
            range_end=body.range_end,
            base_text=body.base_text,
            proposed_text=body.proposed_text,
            rationale=body.rationale,
        )
        s.add(sug)
        await s.flush()
        new_id = sug.id

    await audit.record(
        action="suggestion.add",
        user_id=ident.user_id,
        object_kind="suggestion",
        object_id=new_id,
        payload={"document_id": document_id, "source": body.source},
    )

    async with session_scope() as s:
        sug = await s.get(models.Suggestion, new_id)
        return _to_suggestion_out(sug)


@router.post("/suggestions/{suggestion_id}/accept")
async def accept_suggestion(
    suggestion_id: int,
    ident: identity.Identity = Depends(identity.current_user),
) -> dict:
    return await _resolve_suggestion(suggestion_id, ident, accept=True)


@router.post("/suggestions/{suggestion_id}/reject")
async def reject_suggestion(
    suggestion_id: int,
    ident: identity.Identity = Depends(identity.current_user),
) -> dict:
    return await _resolve_suggestion(suggestion_id, ident, accept=False)


async def _resolve_suggestion(
    suggestion_id: int, ident: identity.Identity, *, accept: bool
) -> dict:
    from backend.documents import service as doc_service
    from backend.documents.splice import StaleSuggestionError, apply_suggestion

    # ── Phase 1: read + RBAC check + extract the splice inputs ──────────
    # No writes here — if we crash later (validation, splice failure) the
    # suggestion stays pending and the user can retry.
    async with session_scope() as s:
        sug = await s.get(models.Suggestion, suggestion_id)
        if sug is None:
            raise HTTPException(404, "suggestion not found")
        if sug.status != models.SuggestionStatus.PENDING:
            raise HTTPException(409, f"suggestion already {sug.status.value}")
        matter_id = await _matter_id_for_document(sug.document_id)
        if matter_id is not None:
            await identity.require_matter_access(matter_id, ident, minimum="editor")
        document_id = sug.document_id
        range_start = sug.range_start
        range_end = sug.range_end
        base_text = sug.base_text
        proposed_text = sug.proposed_text

    # ── Phase 2: on accept, validate the suggestion still applies and
    # write the new document version BEFORE marking resolved. If
    # apply_suggestion raises (range out of bounds / base_text drift),
    # the suggestion remains pending — no DB write happens.
    if accept:
        current = await doc_service.latest_content(document_id)
        if current is None:
            raise HTTPException(404, "document not found")
        try:
            new_content = apply_suggestion(
                current=current,
                range_start=range_start,
                range_end=range_end,
                base_text=base_text,
                proposed_text=proposed_text,
            )
        except StaleSuggestionError as e:
            raise HTTPException(409, e.message)
        await doc_service.new_version(
            document_id, new_content, note=f"accepted suggestion #{suggestion_id}"
        )

    # ── Phase 3: flip the suggestion status. By now any accept-side
    # validation has succeeded, so this is the only step still able to
    # fail — and if it does, we've already created the new version,
    # which is recoverable (the user can manually mark it resolved).
    async with session_scope() as s:
        sug = await s.get(models.Suggestion, suggestion_id)
        if sug is None:
            # Vanished between Phase 1 and Phase 3 — should be impossible
            # in normal use but guard against it.
            raise HTTPException(404, "suggestion not found")
        sug.status = (
            models.SuggestionStatus.ACCEPTED if accept else models.SuggestionStatus.REJECTED
        )
        sug.resolved_by = ident.user_id
        sug.resolved_at = datetime.now(timezone.utc)

    await audit.record(
        action="suggestion.accept" if accept else "suggestion.reject",
        user_id=ident.user_id,
        object_kind="suggestion",
        object_id=suggestion_id,
        payload={"document_id": document_id},
    )
    return {"ok": True, "status": "accepted" if accept else "rejected"}


def _to_suggestion_out(s) -> SuggestionOut:
    return SuggestionOut(
        id=s.id,
        document_id=s.document_id,
        user_id=s.user_id,
        source=s.source,
        range_start=s.range_start,
        range_end=s.range_end,
        base_text=s.base_text,
        proposed_text=s.proposed_text,
        rationale=s.rationale,
        status=s.status.value if hasattr(s.status, "value") else str(s.status),
        created_at=s.created_at.isoformat() if s.created_at else "",
    )


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


class AuditEntryOut(BaseModel):
    id: int
    user_id: str | None
    action: str
    object_kind: str | None
    object_id: str | None
    payload: dict | None
    created_at: str


@router.get("/audit", response_model=list[AuditEntryOut])
async def list_audit(
    limit: int = 100,
    matter_id: int | None = None,
    user_id: str | None = None,
    action: str | None = None,
    ident: identity.Identity = Depends(identity.current_user),
) -> list[AuditEntryOut]:
    # Only owners see the global log; others can filter to their own matters.
    if matter_id is not None:
        await identity.require_matter_access(matter_id, ident, minimum="viewer")
    elif ident.role != "owner":
        raise HTTPException(403, "owner-only")

    async with session_scope() as s:
        q = select(models.AuditLog).order_by(models.AuditLog.id.desc()).limit(limit)
        if matter_id is not None:
            q = q.where(
                models.AuditLog.object_kind == "matter",
                models.AuditLog.object_id == str(matter_id),
            )
        if user_id is not None:
            q = q.where(models.AuditLog.user_id == user_id)
        if action is not None:
            q = q.where(models.AuditLog.action == action)
        rows = (await s.execute(q)).scalars().all()
    return [
        AuditEntryOut(
            id=r.id,
            user_id=r.user_id,
            action=r.action,
            object_kind=r.object_kind,
            object_id=r.object_id,
            payload=r.payload,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _matter_id_for_document(document_id: int) -> int | None:
    async with session_scope() as s:
        doc = await s.get(models.Document, document_id)
        return doc.matter_id if doc else None
