from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from backend.db import models
from backend.db.session import session_scope

router = APIRouter()


@router.get("/stats")
async def stats() -> dict:
    async with session_scope() as s:
        n_per = await s.scalar(select(func.count()).select_from(models.Peraturan))
        n_pasal = await s.scalar(select(func.count()).select_from(models.Pasal))
        n_ayat = await s.scalar(select(func.count()).select_from(models.Ayat))
        n_embedded = await s.scalar(
            select(func.count()).select_from(models.Pasal).where(
                models.Pasal.embedding.isnot(None)
            )
        )
    return {
        "peraturan": n_per or 0,
        "pasal": n_pasal or 0,
        "ayat": n_ayat or 0,
        "embedded": n_embedded or 0,
    }


@router.get("/peraturan")
async def list_peraturan(limit: int = 50) -> list[dict]:
    async with session_scope() as s:
        rows = (
            await s.execute(
                select(models.Peraturan).order_by(models.Peraturan.id).limit(limit)
            )
        ).scalars().all()
    return [
        {
            "id": p.id,
            "jenis": p.jenis.value if hasattr(p.jenis, "value") else p.jenis,
            "nomor": p.nomor,
            "tahun": p.tahun,
            "judul": p.judul,
            "status": p.status.value if hasattr(p.status, "value") else p.status,
        }
        for p in rows
    ]


@router.get("/pasal/{pasal_id}")
async def get_pasal(pasal_id: int) -> dict:
    async with session_scope() as s:
        pasal = await s.get(models.Pasal, pasal_id)
        if not pasal:
            raise HTTPException(404, "pasal not found")
        peraturan = await s.get(models.Peraturan, pasal.peraturan_id)
        ayat = (
            await s.execute(
                select(models.Ayat).where(models.Ayat.pasal_id == pasal_id).order_by(models.Ayat.id)
            )
        ).scalars().all()
        ayat_out = []
        for a in ayat:
            huruf = (
                await s.execute(
                    select(models.Huruf).where(models.Huruf.ayat_id == a.id).order_by(models.Huruf.id)
                )
            ).scalars().all()
            ayat_out.append(
                {
                    "id": a.id,
                    "nomor": a.nomor,
                    "teks": a.teks,
                    "huruf": [{"id": h.id, "huruf": h.huruf, "teks": h.teks} for h in huruf],
                }
            )

    label = _peraturan_label(peraturan)
    return {
        "id": pasal.id,
        "nomor": pasal.nomor,
        "teks": pasal.teks,
        "ayat": ayat_out,
        "peraturan": {
            "id": peraturan.id,
            "jenis": peraturan.jenis.value if hasattr(peraturan.jenis, "value") else peraturan.jenis,
            "nomor": peraturan.nomor,
            "tahun": peraturan.tahun,
            "judul": peraturan.judul,
            "label": label,
        },
    }


@router.post("/embed")
async def embed_pending(limit: int = 1000) -> dict:
    """Embed up to `limit` pasal rows that don't yet have an embedding.

    Synchronous — for dev. In production, dispatch the Celery task
    `rag.embed_pending` instead.
    """
    from backend.rag.embed_runner import embed_pending as runner

    stats = await runner(limit=limit)
    return {"scanned": stats.scanned, "embedded": stats.embedded, "skipped": stats.skipped}


@router.post("/raptor/build")
async def raptor_build(peraturan_ids: list[int] | None = None) -> dict:
    """(Re)build the RAPTOR summary tree over the peraturan corpus.

    Pass `peraturan_ids` to limit to a subset; omit to rebuild the
    whole corpus. Idempotent — existing raptor_node rows for the same
    peraturan_id are wiped first.
    """
    from backend.rag.raptor import build_corpus_tree

    result = await build_corpus_tree(peraturan_ids=peraturan_ids)
    return {
        "nodes_inserted": result.nodes_inserted,
        "levels_built": result.levels_built,
        "skipped_missing_summary": result.skipped_missing_summary,
    }


@router.post("/citation/backfill")
async def citation_backfill(peraturan_id: int | None = None, limit: int | None = None) -> dict:
    """Walk pasal text, parse Pasal references, insert CitationEdge rows.

    `peraturan_id` scopes to one peraturan; omitting it scans the whole
    corpus (use `limit` for chunked rebuilds). Idempotent — duplicate
    edges are silently dropped by the unique constraint.
    """
    from backend.ingest.citation_backfill import backfill_all, backfill_for_peraturan

    if peraturan_id is not None:
        stats = await backfill_for_peraturan(peraturan_id)
    else:
        stats = await backfill_all(limit=limit)
    return {
        "pasal_scanned": stats.pasal_scanned,
        "refs_found": stats.refs_found,
        "edges_inserted": stats.edges_inserted,
        "edges_already_present": stats.edges_already_present,
        "refs_unresolved": stats.refs_unresolved,
    }


@router.post("/ingest/url")
async def ingest_url(url: str, source: str = "bpk") -> dict:
    """Scrape a peraturan URL end-to-end: parse → persist → embed →
    citation backfill → RAPTOR build.

    `source` ∈ {bpk, jdihn}. Returns per-step counts plus the
    `peraturan_id` of the inserted row, or `skipped_reason` if the
    parser couldn't find a pasal body.
    """
    from backend.ingest.orchestrator import ingest_peraturan_url

    result = await ingest_peraturan_url(url, source=source)
    return {
        "peraturan_id": result.peraturan_id,
        "pasal_inserted": result.pasal_inserted,
        "embedded": result.embedded,
        "edges_inserted": result.edges_inserted,
        "raptor_nodes": result.raptor_nodes,
        "skipped_reason": result.skipped_reason,
    }


def _peraturan_label(p) -> str:
    jenis = p.jenis.value if hasattr(p.jenis, "value") else p.jenis
    if jenis in {"KUHP", "KUHPerdata", "KUHAP", "UUD"}:
        return jenis
    return f"{jenis} {p.nomor}/{p.tahun}" if p.nomor else jenis
