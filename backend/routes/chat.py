from fastapi import APIRouter
from pydantic import BaseModel

from backend.agents.harness import AgentHarness

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str | None = None
    agent: str = "asisten_hukum"
    message: str
    as_of: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    citations: list[dict] = []
    trace: list[dict] = []


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    harness = AgentHarness(agent_name=req.agent, session_id=req.session_id)
    result = await harness.run(req.message, as_of=req.as_of)
    return ChatResponse(
        session_id=result.session_id,
        reply=result.reply,
        citations=result.citations,
        trace=result.trace,
    )
