"""End-to-end ingest orchestrator for a single peraturan URL.

Glues scrape → persist → embed → citation backfill → RAPTOR build into
one entry point so admin endpoints (and a future Celery task) can call
a single function.

Each step is best-effort: if the embedding step fails (no model
installed in this env) we still persist the peraturan; if RAPTOR build
fails we still log the upserted rows. The result carries per-step
counts so the caller can surface them in a success toast.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

_log = logging.getLogger(__name__)


@dataclass(slots=True)
class IngestPeraturanResult:
    peraturan_id: int | None
    pasal_inserted: int
    embedded: int
    edges_inserted: int
    raptor_nodes: int
    skipped_reason: str | None = None


async def ingest_peraturan_url(
    url: str,
    *,
    source: str = "bpk",
    do_embed: bool = True,
    do_citation_backfill: bool = True,
    do_raptor: bool = True,
) -> IngestPeraturanResult:
    """Scrape a peraturan URL and ingest end-to-end.

    `source` is "bpk" or "jdihn"; the parser is identical for now but
    we keep the parameter so future provenance tracking can record
    which scraper produced the row.
    """
    if source == "bpk":
        from backend.ingest.scrapers.bpk import scrape_bpk_url

        parsed = await scrape_bpk_url(url)
    elif source == "jdihn":
        from backend.ingest.scrapers.jdihn import scrape_jdihn_url

        parsed = await scrape_jdihn_url(url)
    else:
        raise ValueError(f"unknown source {source!r}")

    if not parsed.pasal:
        return IngestPeraturanResult(
            peraturan_id=None,
            pasal_inserted=0,
            embedded=0,
            edges_inserted=0,
            raptor_nodes=0,
            skipped_reason="parser returned no pasal — check the source page",
        )

    peraturan_id, pasal_count = await _persist_parsed(parsed)

    embedded = 0
    if do_embed:
        try:
            from backend.rag.embed_runner import embed_pending

            stats = await embed_pending(limit=10_000)
            embedded = stats.embedded
        except Exception as e:  # noqa: BLE001
            _log.warning("ingest: embed step failed: %s", e)

    edges = 0
    if do_citation_backfill and peraturan_id is not None:
        try:
            from backend.ingest.citation_backfill import backfill_for_peraturan

            s = await backfill_for_peraturan(peraturan_id)
            edges = s.edges_inserted
        except Exception as e:  # noqa: BLE001
            _log.warning("ingest: citation backfill failed: %s", e)

    raptor_nodes = 0
    if do_raptor and peraturan_id is not None:
        try:
            from backend.rag.raptor import build_corpus_tree

            r = await build_corpus_tree(peraturan_ids=[peraturan_id])
            raptor_nodes = r.nodes_inserted
        except Exception as e:  # noqa: BLE001
            _log.warning("ingest: raptor build failed: %s", e)

    return IngestPeraturanResult(
        peraturan_id=peraturan_id,
        pasal_inserted=pasal_count,
        embedded=embedded,
        edges_inserted=edges,
        raptor_nodes=raptor_nodes,
    )


async def _persist_parsed(parsed) -> tuple[int, int]:
    """Persist a ParsedPeraturan into Peraturan / Pasal / Ayat / Huruf.

    Reuses the seed_loader-style semantics: skip insertion if a row
    with the same (jenis, nomor, tahun) already exists. Returns
    (peraturan_id, pasal_inserted).
    """
    from sqlalchemy import select

    from backend.db import models
    from backend.db.session import session_scope

    async with session_scope() as s:
        existing = (
            await s.execute(
                select(models.Peraturan).where(
                    models.Peraturan.jenis == models.JenisPeraturan(parsed.jenis),
                    models.Peraturan.nomor == parsed.nomor,
                    models.Peraturan.tahun == parsed.tahun,
                )
            )
        ).scalar_one_or_none()
        if existing:
            return existing.id, 0

        per = models.Peraturan(
            jenis=models.JenisPeraturan(parsed.jenis),
            nomor=parsed.nomor,
            tahun=parsed.tahun,
            judul=parsed.judul or "(tanpa judul)",
            tentang=parsed.tentang,
            status=models.StatusPeraturan(parsed.status or "berlaku"),
            penerbit=parsed.penerbit,
            source_url=parsed.source_url,
        )
        s.add(per)
        await s.flush()
        pasal_inserted = 0
        for p in parsed.pasal:
            pasal_row = models.Pasal(peraturan_id=per.id, nomor=p.nomor, teks=p.teks)
            s.add(pasal_row)
            await s.flush()
            pasal_inserted += 1
            for a in p.ayat:
                ayat_row = models.Ayat(
                    pasal_id=pasal_row.id, nomor=a["nomor"], teks=a.get("teks", "")
                )
                s.add(ayat_row)
                await s.flush()
                for h in a.get("huruf", []) or []:
                    s.add(
                        models.Huruf(
                            ayat_id=ayat_row.id,
                            huruf=h["huruf"],
                            teks=h.get("teks", ""),
                        )
                    )
        return per.id, pasal_inserted
