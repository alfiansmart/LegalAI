"""Embed pasal rows whose embedding column is NULL.

Run sync (no Celery) via:
    docker compose exec backend python -m backend.rag.embed_runner

Or programmatically via `embed_pending(limit=...)`.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy import select, update

from backend.db import models
from backend.db.session import session_scope


@dataclass(slots=True)
class EmbedStats:
    scanned: int
    embedded: int
    skipped: int


def _compose_text(pasal_teks: str, ayat: list[tuple[str, str]]) -> str:
    parts = [pasal_teks or ""]
    for nomor, teks in ayat:
        parts.append(f"({nomor}) {teks}")
    return "\n".join(p for p in parts if p).strip()


async def embed_pending(limit: int = 1000) -> EmbedStats:
    from backend.rag.embeddings import embed  # heavy import — lazy

    scanned = embedded = skipped = 0

    async with session_scope() as s:
        rows = (
            await s.execute(
                select(models.Pasal).where(models.Pasal.embedding.is_(None)).limit(limit)
            )
        ).scalars().all()

        for pasal in rows:
            scanned += 1
            ayat_rows = (
                await s.execute(
                    select(models.Ayat.nomor, models.Ayat.teks).where(
                        models.Ayat.pasal_id == pasal.id
                    )
                )
            ).all()
            ayat = [(a.nomor, a.teks) for a in ayat_rows]
            composed = _compose_text(pasal.teks, ayat)
            if not composed:
                skipped += 1
                continue
            [vec] = embed([composed], is_query=False)
            await s.execute(
                update(models.Pasal).where(models.Pasal.id == pasal.id).values(embedding=vec)
            )
            embedded += 1

    return EmbedStats(scanned=scanned, embedded=embedded, skipped=skipped)


async def main() -> None:
    stats = await embed_pending(limit=10_000)
    print(f"[embed] scanned={stats.scanned} embedded={stats.embedded} skipped={stats.skipped}")


if __name__ == "__main__":
    asyncio.run(main())
