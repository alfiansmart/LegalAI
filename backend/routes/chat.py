import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from backend.agents import slash
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
    trace: list[dict] = []


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    session_id = req.session_id
    agent_name = req.agent
    plan_mode = req.plan_mode
    user_message = req.message

    # Slash-command rewriting (without exposing a new endpoint).
    if slash.is_slash(user_message):
        intent = slash.parse(user_message)
        if intent is not None:
            # `/help` and unknown commands return immediately without the LLM.
            if intent.help_text:
                return ChatResponse(
                    session_id=session_id or uuid.uuid4().hex,
                    reply=intent.help_text,
                )
            # `/clear` starts a fresh session.
            if intent.command == "clear":
                return ChatResponse(
                    session_id=uuid.uuid4().hex,
                    reply="🆕 Sesi baru dimulai.",
                )
            # Persona override (e.g. /agent drafter or auto-bound by /draft).
            if intent.agent:
                agent_name = intent.agent
            if intent.plan_mode:
                plan_mode = True
            user_message = slash.to_user_message(intent)

    harness = AgentHarness(
        agent_name=agent_name,
        session_id=session_id,
        matter_id=req.matter_id,
    )
    result = await harness.run(user_message, as_of=req.as_of, plan_mode=plan_mode)
    return ChatResponse(
        session_id=result.session_id,
        reply=result.reply,
        citations=[CitationOut(**c) for c in result.citations],
        trace=result.trace,
    )


@router.get("/commands")
def list_commands() -> list[dict]:
    return [
        {"name": name, **spec, "trigger": f"/{name}"}
        for name, spec in slash.COMMANDS.items()
    ]
