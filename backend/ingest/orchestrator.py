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

    Phase 8: also runs the promulgation parser over the raw text so
    `tanggal_diundangkan`, `lembaran_negara`, `effective_from`, the
    `ditetapkan_di` city and the hierarchy level all land on the row.
    Repealed / amended peraturan refs are resolved into CitationEdge
    rows here as well — that closes the "what does this kill" half of
    the knowledge graph that flat ingest leaves out.
    """
    from sqlalchemy import select

    from backend.db import models
    from backend.db.session import session_scope
    from backend.legal.hierarchy import level_of
    from backend.legal.promulgation import parse_promulgation

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

        # Compose the haystack the promulgation parser scans: the body
        # text we just parsed (the parser also receives the original
        # cleartext via parsed.tentang when available, but the closing
        # clauses usually live in the body). We rebuild a flat string
        # because Phase 6's parser only kept the structural pasal/ayat
        # tree.
        body_text = "\n".join(
            (p.teks or "")
            + ("\n" + "\n".join(f"({a['nomor']}) {a.get('teks', '')}" for a in p.ayat) if p.ayat else "")
            for p in parsed.pasal
        )
        promul = parse_promulgation(body_text)

        per = models.Peraturan(
            jenis=models.JenisPeraturan(parsed.jenis),
            nomor=parsed.nomor,
            tahun=parsed.tahun,
            judul=parsed.judul or "(tanpa judul)",
            tentang=parsed.tentang,
            status=models.StatusPeraturan(parsed.status or "berlaku"),
            penerbit=parsed.penerbit,
            source_url=parsed.source_url,
            hierarchy_level=level_of(parsed.jenis),
            ditetapkan_di=promul.ditetapkan_di,
            tanggal_ditetapkan=promul.tanggal_ditetapkan,
            tanggal_diundangkan=promul.tanggal_diundangkan,
            lembaran_negara=promul.lembaran_negara,
            tambahan_lembaran_negara=promul.tambahan_lembaran_negara,
            berita_negara=promul.berita_negara,
        )
        s.add(per)
        await s.flush()
        # Resolve repealed / amended references → CitationEdge rows.
        # Best-effort: failures don't fail the ingest.
        try:
            await _record_repeal_amend_edges(per.id, promul)
        except Exception as e:  # noqa: BLE001
            _log.warning(
                "_persist_parsed: repeal/amend edge resolution failed: %s", e
            )
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


async def _record_repeal_amend_edges(src_peraturan_id: int, promul) -> None:
    """Resolve "Peraturan X dicabut" / "sebagaimana telah diubah dengan Peraturan Y"
    references into CitationEdge rows.

    Each referenced peraturan is looked up by (jenis, nomor, tahun); when
    found, we insert an edge from the *first* pasal of the source row to
    the *first* pasal of the target. CitationEdge is a pasal-level graph
    in the current schema; future work may add a peraturan-level edge
    table, but for now the first-pasal anchor is a faithful proxy.
    """
    import re

    from sqlalchemy import select

    from backend.db import models
    from backend.db.session import session_scope

    _REF_PARSE_RE = re.compile(
        r"(?P<jenis>[A-Za-z][A-Za-z .]+?)\s+No\.?\s*(?P<no>[A-Za-z0-9./-]+)"
        r"\s+Tahun\s+(?P<year>\d{4})",
        re.I,
    )

    def _refs_with_kind() -> list[tuple[str, str, str, str, str]]:
        from backend.rag.citation import _normalise_jenis  # type: ignore

        out: list[tuple[str, str, str, str, str]] = []
        for raw in promul.repealed_refs:
            m = _REF_PARSE_RE.search(raw)
            if m:
                canon, _ = _normalise_jenis(m["jenis"])
                out.append(
                    (canon, m["no"], m["year"], "repeals", raw)
                )
        for raw in promul.amended_refs:
            m = _REF_PARSE_RE.search(raw)
            if m:
                canon, _ = _normalise_jenis(m["jenis"])
                # Direction: this row is *amending* the older row; the edge
                # source is the new row, destination is the older one.
                out.append(
                    (canon, m["no"], m["year"], "amends", raw)
                )
        return out

    refs = _refs_with_kind()
    if not refs:
        return

    async with session_scope() as s:
        # First pasal of the source peraturan.
        src_pasal = (
            (
                await s.execute(
                    select(models.Pasal.id)
                    .where(models.Pasal.peraturan_id == src_peraturan_id)
                    .order_by(models.Pasal.id)
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )
        if src_pasal is None:
            return

        for canon, no, year, kind_str, raw in refs:
            try:
                target_per = (
                    await s.execute(
                        select(models.Peraturan).where(
                            models.Peraturan.jenis == models.JenisPeraturan(canon),
                            models.Peraturan.nomor == no,
                            models.Peraturan.tahun == int(year),
                        )
                    )
                ).scalar_one_or_none()
            except ValueError:
                # Unknown JenisPeraturan token; skip silently.
                continue
            if target_per is None:
                continue
            target_pasal = (
                (
                    await s.execute(
                        select(models.Pasal.id)
                        .where(models.Pasal.peraturan_id == target_per.id)
                        .order_by(models.Pasal.id)
                        .limit(1)
                    )
                )
                .scalars()
                .first()
            )
            if target_pasal is None:
                continue
            try:
                kind_enum = models.CitationKind(kind_str)
            except ValueError:
                kind_enum = models.CitationKind.REFERS
            s.add(
                models.CitationEdge(
                    src_pasal_id=src_pasal,
                    dst_pasal_id=target_pasal,
                    kind=kind_enum,
                )
            )
            try:
                await s.flush()
            except Exception:  # noqa: BLE001 — duplicate key, race, etc.
                await s.rollback()
