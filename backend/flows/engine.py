"""Flow engine — executes a DAG of skill/tool/LLM/condition/loop/human-approval nodes.

Flows are JSON DAGs. Execution streams progress over WebSocket to the UI.
Heavy node executions are dispatched to Celery.

Node schema:
    {"id": "n1", "type": "skill", "skill": "peraturan_search",
     "args": {...}, "next": ["n2"]}

Edge schema (in `edges`):
    {"from": "n1", "to": "n2", "when": "$.result.score > 0.5"}
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path


class FlowEngine:
    async def start(self, flow_slug: str, inputs: dict) -> str:
        run_id = uuid.uuid4().hex
        # Phase-0 stub — load definition, validate, schedule first node.
        defn = _load_flow(flow_slug)
        if not defn:
            raise ValueError(f"flow {flow_slug!r} not found")
        # TODO: persist FlowRun, schedule via Celery, stream over WS.
        return run_id


def _load_flow(slug: str) -> dict | None:
    p = Path("flows") / f"{slug}.json"
    if p.exists():
        return json.loads(p.read_text())
    return None
