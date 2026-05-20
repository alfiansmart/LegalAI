"""Free-form chat endpoint.

Free-form chat is the secondary surface in the workspace — the six task
buttons cover ~90% of legal work; chat is the fallback for "I don't
know which button I want." The slash-command palette that existed in
Phase 3 has been removed entirely per product decision.

The endpoint is a thin wrapper around AgentHarness; it threads
`matter_id` through (so `MATTER.md` is injected into the system prompt)
and surfaces the agent's structured outputs: text reply, resolved
pasal citations, visual artifacts, and the tool trace.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from backend.agents.harness import AgentHarness

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str | None = None
    agent: str = "asisten_hukum"
    message: str
    as_of: str | None = None
    plan_mode: bool = False
    matter_id: int | None = None


class CitationOut(BaseModel):
    label: str
    peraturan: str
    pasal: str
    ayat: str | None = None
    huruf: str | None = None
    pasal_id: int | None = None
    verified: bool


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    citations: list[CitationOut] = []
    artifacts: list[dict] = []
    trace: list[dict] = []


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    harness = AgentHarness(
        agent_name=req.agent,
        session_id=req.session_id,
        matter_id=req.matter_id,
    )
    result = await harness.run(req.message, as_of=req.as_of, plan_mode=req.plan_mode)
    return ChatResponse(
        session_id=result.session_id,
        reply=result.reply,
        citations=[CitationOut(**c) for c in result.citations],
        artifacts=result.artifacts,
        trace=result.trace,
    )
