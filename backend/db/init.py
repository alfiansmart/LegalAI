"""Dev convenience: create any tables missing from the DB on app startup.

This is a pragmatic fallback for the scaffold phase — production
deployments should rely on `alembic upgrade head`. We only create
*missing* tables (SQLAlchemy's `create_all` is idempotent and never
drops or alters existing tables).
"""
from __future__ import annotations

from backend.db.models import Base
from backend.db.session import engine


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
