from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.routes import agents, chat, corpus, documents, flows, health, search, skills


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.skills_loader import SkillRegistry

    app.state.settings = get_settings()
    app.state.skills = SkillRegistry.from_dir(app.state.settings.skills_dir)
    yield


app = FastAPI(
    title="LegalAI",
    description="Indonesian Legal Agent Platform",
    version="0.0.1",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(search.router, prefix="/search", tags=["search"])
app.include_router(agents.router, prefix="/agents", tags=["agents"])
app.include_router(skills.router, prefix="/skills", tags=["skills"])
app.include_router(corpus.router, prefix="/corpus", tags=["corpus"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(flows.router, prefix="/flows", tags=["flows"])
