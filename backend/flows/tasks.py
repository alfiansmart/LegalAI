"""Celery tasks for Flow node execution."""
from __future__ import annotations

from backend.worker import celery_app


@celery_app.task(name="flows.run_node")
def run_node(run_id: str, node_id: str) -> None:
    raise NotImplementedError
