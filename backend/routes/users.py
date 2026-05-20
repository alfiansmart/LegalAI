"""User + token management.

Minimal endpoints for self-hosted firms:
  - POST /users           — create a user (returns one-time-display token)
  - GET  /users/me        — who am I (driven by Authorization header)
  - POST /users/{id}/token — rotate / reissue API token
  - GET  /users           — list (owner-only)

No SSO yet; tokens are random opaque strings. The first user that
hits `POST /users` is automatically promoted to UserRole.OWNER so a
fresh deploy can bootstrap itself.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select

from backend.auth import audit, identity, tokens
from backend.db import models
from backend.db.session import session_scope

router = APIRouter()


class UserIn(BaseModel):
    email: EmailStr
    name: str
    role: str = "lawyer"


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    is_active: bool


class CreateUserResponse(BaseModel):
    user: UserOut
    token: str  # one-time display — store it somewhere safe


@router.get("/me", response_model=UserOut)
async def me(ident: identity.Identity = Depends(identity.current_user)) -> UserOut:
    return UserOut(
        id=ident.user_id,
        email=ident.email or "",
        name=ident.name,
        role=ident.role,
        is_active=True,
    )


@router.post("", response_model=CreateUserResponse)
async def create_user(
    body: UserIn,
    ident: identity.Identity = Depends(identity.current_user),
) -> CreateUserResponse:
    # Bootstrapping rule: if there are zero users yet, anyone can create
    # the first one and it auto-becomes OWNER. After that, only OWNER
    # users can mint new accounts.
    async with session_scope() as s:
        existing_count = (
            await s.execute(select(func.count()).select_from(models.User))
        ).scalar_one()
        if existing_count > 0 and ident.role != "owner":
            raise HTTPException(403, "only owners can create users")

        try:
            role = models.UserRole(body.role)
        except ValueError:
            raise HTTPException(400, f"unknown role {body.role!r}")
        if existing_count == 0:
            role = models.UserRole.OWNER  # bootstrap promotion

        # Email uniqueness
        if (
            await s.execute(
                select(models.User).where(models.User.email == str(body.email))
            )
        ).scalar_one_or_none():
            raise HTTPException(409, "email already registered")

        raw_token, token_hash = tokens.issue_token()
        user = models.User(
            id=uuid.uuid4().hex,
            email=str(body.email),
            name=body.name,
            role=role,
            api_token_hash=token_hash,
        )
        s.add(user)
        await s.flush()
        result = CreateUserResponse(
            user=UserOut(
                id=user.id,
                email=user.email,
                name=user.name,
                role=user.role.value,
                is_active=user.is_active,
            ),
            token=raw_token,
        )

    await audit.record(
        action="user.create",
        user_id=ident.user_id,
        object_kind="user",
        object_id=result.user.id,
        payload={"email": result.user.email, "role": result.user.role},
    )
    return result


@router.post("/{user_id}/token", response_model=dict)
async def rotate_token(
    user_id: str,
    ident: identity.Identity = Depends(identity.current_user),
) -> dict:
    # Only OWNER or the user themselves can rotate their own token.
    if ident.role != "owner" and ident.user_id != user_id:
        raise HTTPException(403, "cannot rotate someone else's token")

    raw_token, token_hash = tokens.issue_token()
    async with session_scope() as s:
        u = await s.get(models.User, user_id)
        if u is None:
            raise HTTPException(404, "user not found")
        u.api_token_hash = token_hash

    await audit.record(
        action="user.token_rotate",
        user_id=ident.user_id,
        object_kind="user",
        object_id=user_id,
    )
    return {"token": raw_token}


@router.get("", response_model=list[UserOut])
async def list_users(
    ident: identity.Identity = Depends(identity.current_user),
) -> list[UserOut]:
    if ident.role != "owner":
        raise HTTPException(403, "owner-only")
    async with session_scope() as s:
        rows = (await s.execute(select(models.User).order_by(models.User.created_at))).scalars().all()
    return [
        UserOut(
            id=u.id,
            email=u.email,
            name=u.name,
            role=u.role.value,
            is_active=u.is_active,
        )
        for u in rows
    ]
