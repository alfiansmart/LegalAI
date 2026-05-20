"""Resolve the calling user from the Authorization header.

`current_user()` is a FastAPI dependency that returns the authenticated
User row, or a synthetic "public" user when no token is supplied. The
synthetic user is read-only on collaboration features (comments,
suggestions, audit-log writes are still allowed but stamped with the
public id so abuse is at least traceable).

`require_matter_access(matter_id, role)` enforces RBAC on matter-
scoped endpoints. Roles ladder: viewer < reviewer < editor < owner.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# FastAPI is optional at import time so the pure RBAC helpers below
# (`_rank`, `_ROLE_LADDER`) stay testable in environments that don't
# ship fastapi. When fastapi *is* present we expose `current_user` as
# a proper dependency with Header / Request annotations.
try:
    from fastapi import Header as _Header, HTTPException as _HTTPException, Request as _Request

    _HAS_FASTAPI = True
except ImportError:  # pragma: no cover — only hit in test/dev envs without fastapi
    _HAS_FASTAPI = False
    _Header = None  # type: ignore[assignment]
    _HTTPException = Exception  # type: ignore[assignment]
    _Request = None  # type: ignore[assignment]

_PUBLIC_USER_ID = "public"
_PUBLIC_USER_NAME = "Public Demo User"


@dataclass(slots=True)
class Identity:
    user_id: str
    name: str
    email: str | None
    role: str  # "owner" | "lawyer" | "paralegal" | "client" | "public"
    is_authenticated: bool


_PUBLIC = Identity(
    user_id=_PUBLIC_USER_ID,
    name=_PUBLIC_USER_NAME,
    email=None,
    role="public",
    is_authenticated=False,
)


async def _resolve(authorization: str | None) -> Identity:
    """Pure resolver: header value → Identity. No FastAPI dependency."""
    if not authorization:
        return _PUBLIC

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        # Malformed header — don't 401, just treat as public. Lets demo
        # endpoints keep working when a UI client forgets to attach a token.
        return _PUBLIC

    ident = await _lookup_token(token)
    if ident is None:
        if _HAS_FASTAPI:
            raise _HTTPException(status_code=401, detail="invalid or expired token")
        return _PUBLIC
    return ident


if _HAS_FASTAPI:

    async def current_user(
        request: _Request,
        authorization: str | None = _Header(default=None),
    ) -> Identity:
        """FastAPI dependency: resolve the calling user."""
        ident = await _resolve(authorization)
        try:
            request.state.identity = ident
        except Exception:  # noqa: BLE001 — non-Starlette request in tests
            pass
        return ident

else:  # pragma: no cover — exercised only in test env without fastapi

    async def current_user(  # type: ignore[no-redef]
        request: Any = None,
        authorization: str | None = None,
    ) -> Identity:
        return await _resolve(authorization)


async def _lookup_token(token: str) -> Identity | None:
    from sqlalchemy import select

    from backend.auth.tokens import hash_token
    from backend.db import models
    from backend.db.session import session_scope

    h = hash_token(token)
    async with session_scope() as s:
        user = (
            await s.execute(
                select(models.User).where(
                    models.User.api_token_hash == h, models.User.is_active.is_(True)
                )
            )
        ).scalar_one_or_none()
        if user is None:
            return None
        # Touch last_login_at (best-effort).
        from datetime import datetime, timezone

        user.last_login_at = datetime.now(timezone.utc)
        return Identity(
            user_id=user.id,
            name=user.name,
            email=user.email,
            role=user.role.value if hasattr(user.role, "value") else str(user.role),
            is_authenticated=True,
        )


# ---------- RBAC -----------------------------------------------------------


_ROLE_LADDER = {"viewer": 0, "reviewer": 1, "editor": 2, "owner": 3}


def _rank(role: str) -> int:
    return _ROLE_LADDER.get(role, -1)


async def require_matter_access(
    matter_id: int, identity: Identity, *, minimum: str = "viewer"
) -> str:
    """Verify the identity has at least `minimum` access on the matter.

    Returns the user's actual role on the matter (e.g. "editor"). Raises
    HTTPException(403) on insufficient access. Owners of the workspace
    user-account (role=='owner') get implicit access to every matter
    without an explicit MatterMember row.
    """
    if identity.role == "owner":
        return "owner"

    from sqlalchemy import select

    from backend.db import models
    from backend.db.session import session_scope

    async with session_scope() as s:
        member = (
            await s.execute(
                select(models.MatterMember).where(
                    models.MatterMember.matter_id == matter_id,
                    models.MatterMember.user_id == identity.user_id,
                )
            )
        ).scalar_one_or_none()

    # No row → no access (except for the public-mode legacy compatibility
    # below). The owner-bypass above is the only escape hatch.
    if member is None:
        # Public/legacy mode: if there are zero MatterMember rows for
        # this matter, treat the matter as unrestricted. This keeps
        # single-user dev demos working until a firm explicitly adds
        # members.
        async with session_scope() as s:
            any_member = (
                await s.execute(
                    select(models.MatterMember.id).where(
                        models.MatterMember.matter_id == matter_id
                    ).limit(1)
                )
            ).scalar_one_or_none()
        if any_member is None:
            return "editor"  # legacy unrestricted access
        raise HTTPException(403, "matter access denied")

    role = member.role.value if hasattr(member.role, "value") else str(member.role)
    if _rank(role) < _rank(minimum):
        raise HTTPException(403, f"requires {minimum!r}, have {role!r}")
    return role
