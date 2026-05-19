from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class FlowDef(BaseModel):
    id: str
    name: str
    description: str
    nodes: list[dict]
    edges: list[dict]


@router.get("")
def list_flows() -> list[dict]:
    """Return saved flow definitions (starter templates from /flows + user flows)."""
    import json
    import pathlib

    out = []
    p = pathlib.Path("flows")
    if p.exists():
        for f in p.glob("*.json"):
            out.append(json.loads(f.read_text()))
    return out


class RunFlowRequest(BaseModel):
    flow_id: str
    inputs: dict = {}


@router.post("/run")
async def run_flow(req: RunFlowRequest) -> dict:
    from backend.flows.engine import FlowEngine

    engine = FlowEngine()
    run_id = await engine.start(req.flow_id, req.inputs)
    return {"run_id": run_id, "status": "started"}
