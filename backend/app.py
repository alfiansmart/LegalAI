from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.routes import (
    agents,
    chat,
    collab,
    corpus,
    documents,
    flows,
    health,
    matters,
    search,
    skills,
    tasks,
    users,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.db.init import init_db
    from backend.skills_loader import SkillRegistry

    app.state.settings = get_settings()
    app.state.skills = SkillRegistry.from_dir(app.state.settings.skills_dir)
    try:
        await init_db()
    except Exception as e:  # noqa: BLE001 — dev convenience; alembic is the source of truth
        import sys

        print(f"[db] init_db skipped: {e}", file=sys.stderr)
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
app.include_router(matters.router, prefix="/matters", tags=["matters"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
app.include_router(flows.router, prefix="/flows", tags=["flows"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(collab.router, tags=["collaboration"])
