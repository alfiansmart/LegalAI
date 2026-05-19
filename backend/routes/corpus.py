from fastapi import APIRouter

router = APIRouter()


@router.get("/stats")
async def stats() -> dict:
    from backend.db.session import session_scope
    from backend.db import models

    async with session_scope() as s:
        n_per = await s.scalar(models.count(models.Peraturan))
        n_pasal = await s.scalar(models.count(models.Pasal))
        n_ayat = await s.scalar(models.count(models.Ayat))
    return {"peraturan": n_per, "pasal": n_pasal, "ayat": n_ayat}
