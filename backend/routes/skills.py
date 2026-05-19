from fastapi import APIRouter, Request

router = APIRouter()


@router.get("")
def list_skills(request: Request) -> list[dict]:
    registry = request.app.state.skills
    return [s.manifest for s in registry.all()]


@router.get("/{skill_id}")
def get_skill(skill_id: str, request: Request) -> dict:
    registry = request.app.state.skills
    return registry.get(skill_id).manifest
