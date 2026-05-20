"""Append-only audit log writer.

Anywhere in the code path where a consequential write happens
(create matter, upload doc, run a task, accept a suggestion), call
`record(action, ...)`. Best-effort — failures are logged but never
fail the upstream request.
"""
from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)


async def record(
    *,
    action: str,
    user_id: str | None,
    object_kind: str | None = None,
    object_id: str | int | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Write one AuditLog row. Never raises."""
    try:
        from backend.db import models
        from backend.db.session import session_scope

        async with session_scope() as s:
            s.add(
                models.AuditLog(
                    user_id=user_id,
                    action=action,
                    object_kind=object_kind,
                    object_id=str(object_id) if object_id is not None else None,
                    payload=payload,
                )
            )
    except Exception as e:  # noqa: BLE001
        _log.warning("audit.record failed for action=%s: %s", action, e)
