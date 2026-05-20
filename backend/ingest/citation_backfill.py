"""Walk the peraturan corpus and infer CitationEdge rows from pasal text.

For every pasal in scope:
  1. Run `parse_citations` over its text + ayat text + huruf text.
  2. Resolve each CitationRef via `pasal_as_of` to a target pasal_id.
  3. Insert a CitationEdge(src=pasal.id, dst=resolved.id, kind=…).

`kind` defaults to REFERS. Amendment / repeal / dasar-hukum kinds need
a richer signal (verbs like "mencabut", "mengubah") — we tag them with
a tiny rules layer over the surrounding text window.

Idempotent: the UniqueConstraint(src, dst, kind) on CitationEdge means
re-running this is safe; we use `ON CONFLICT DO NOTHING` semantics via
duplicate-key suppression.

Useful when:
  - bulk corpus ingest just landed thousands of new pasal,
  - the citation parser regex gets improved and we want to recompute,
  - a real peraturan replaces a seed stub.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

_log = logging.getLogger(__name__)


@dataclass(slots=True)
class BackfillStats:
    pasal_scanned: int = 0
    refs_found: int = 0
    edges_inserted: int = 0
    edges_already_present: int = 0
    refs_unresolved: int = 0


# Regex windows around a Pasal mention that bump the citation kind up
# from plain REFERS to something more specific.
_AMEND_RE = re.compile(r"\b(mengubah|diubah|perubahan|amendemen)\b", re.I)
_REPEAL_RE = re.compile(r"\b(mencabut|dicabut|tidak\s+berlaku\s+lagi)\b", re.I)
_DASAR_RE = re.compile(r"\b(dasar\s+hukum|berdasarkan|menurut|mengingat)\b", re.I)
_IMPL_RE = re.compile(r"\b(melaksanakan|pelaksanaan|peraturan\s+pelaksana)\b", re.I)


def _infer_kind(text_window: str, default: str = "refers") -> str:
    """Pick a citation kind from a small text window around a Pasal mention."""
    if _REPEAL_RE.search(text_window):
        return "repeals"
    if _AMEND_RE.search(text_window):
        return "amends"
    if _IMPL_RE.search(text_window):
        return "implements"
    if _DASAR_RE.search(text_window):
        return "dasar_hukum"
    return default


def _extract_refs_with_kind(text: str) -> list[tuple]:
    """Parse citations and tag each with an inferred kind.

    Returns list of (CitationRef, kind_str) pairs. Pure-text — no DB.

    The verb that determines the kind in Indonesian legal text almost
    always precedes the Pasal reference ("Mengubah Pasal 5",
    "Mencabut Pasal 6", "Mengingat Pasal 27 UUD 1945"). We look at a
    tight ~50-char window *before* the ref and clip at the previous
    citation if one is closer — so verbs don't leak across siblings
    in a list like "mengubah Pasal 5 dan mencabut Pasal 6".
    """
    from backend.rag.citation import parse_citations

    refs = parse_citations(text)
    # Pre-compute each ref's start offset so we can clip windows.
    starts: list[int] = []
    cursor = 0
    for ref in refs:
        idx = text.find(ref.raw, cursor) if ref.raw else -1
        starts.append(idx)
        if idx >= 0:
            cursor = idx + len(ref.raw)

    out: list[tuple] = []
    for i, ref in enumerate(refs):
        idx = starts[i]
        if idx < 0:
            out.append((ref, "refers"))
            continue
        # Window: from the end of the previous ref (or 50 chars back,
        # whichever is closer) up to the start of this ref.
        prev_end = (
            starts[i - 1] + len(refs[i - 1].raw or "")
            if i > 0 and starts[i - 1] >= 0
            else max(0, idx - 50)
        )
        window_start = max(prev_end, idx - 50)
        window = text[window_start:idx]
        out.append((ref, _infer_kind(window)))
    return out


async def backfill_for_peraturan(peraturan_id: int) -> BackfillStats:
    """Backfill citation edges for every pasal in one peraturan."""
    from sqlalchemy import select

    from backend.db import models
    from backend.db.session import session_scope

    stats = BackfillStats()
    async with session_scope() as s:
        pasals = (
            (
                await s.execute(
                    select(models.Pasal)
                    .where(models.Pasal.peraturan_id == peraturan_id)
                    .order_by(models.Pasal.id)
                )
            )
            .scalars()
            .all()
        )
    for pasal in pasals:
        s_ = await _backfill_one_pasal(pasal)
        stats.pasal_scanned += s_.pasal_scanned
        stats.refs_found += s_.refs_found
        stats.edges_inserted += s_.edges_inserted
        stats.edges_already_present += s_.edges_already_present
        stats.refs_unresolved += s_.refs_unresolved
    return stats


async def backfill_all(limit: int | None = None) -> BackfillStats:
    """Backfill citation edges across the whole corpus.

    `limit` bounds the number of *peraturan* (not pasal) processed in
    one run — useful when chunking large rebuilds.
    """
    from sqlalchemy import select

    from backend.db import models
    from backend.db.session import session_scope

    async with session_scope() as s:
        q = select(models.Peraturan.id).order_by(models.Peraturan.id)
        if limit is not None:
            q = q.limit(limit)
        per_ids = [r[0] for r in (await s.execute(q)).all()]

    stats = BackfillStats()
    for pid in per_ids:
        s_ = await backfill_for_peraturan(pid)
        stats.pasal_scanned += s_.pasal_scanned
        stats.refs_found += s_.refs_found
        stats.edges_inserted += s_.edges_inserted
        stats.edges_already_present += s_.edges_already_present
        stats.refs_unresolved += s_.refs_unresolved
    return stats


async def _backfill_one_pasal(pasal) -> BackfillStats:
    """Process one pasal: parse + resolve + insert edges."""
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError

    from backend.db import models
    from backend.db.session import session_scope
    from backend.rag.temporal import pasal_as_of

    stats = BackfillStats(pasal_scanned=1)

    # Compose the haystack — pasal text + ayat text + huruf text so
    # references inside ayat/huruf are caught too.
    parts: list[str] = [pasal.teks or ""]
    async with session_scope() as s:
        ayats = (
            (
                await s.execute(
                    select(models.Ayat).where(models.Ayat.pasal_id == pasal.id)
                )
            )
            .scalars()
            .all()
        )
        for a in ayats:
            parts.append(f"({a.nomor}) {a.teks}")
            hurufs = (
                (
                    await s.execute(
                        select(models.Huruf).where(models.Huruf.ayat_id == a.id)
                    )
                )
                .scalars()
                .all()
            )
            for h in hurufs:
                parts.append(f"{h.huruf}. {h.teks}")
    haystack = "\n".join(p for p in parts if p).strip()
    if not haystack:
        return stats

    refs_with_kind = _extract_refs_with_kind(haystack)
    stats.refs_found = len(refs_with_kind)
    if not refs_with_kind:
        return stats

    for ref, kind_str in refs_with_kind:
        if not ref.jenis or not ref.pasal:
            stats.refs_unresolved += 1
            continue
        resolved = await pasal_as_of(
            peraturan_jenis=ref.jenis,
            peraturan_nomor=ref.nomor,
            peraturan_tahun=ref.tahun,
            pasal_nomor=ref.pasal,
            ayat_nomor=ref.ayat,
            huruf=ref.huruf,
        )
        dst_id = (resolved or {}).get("id")
        if not dst_id or dst_id == pasal.id:
            stats.refs_unresolved += 1
            continue

        try:
            kind_enum = models.CitationKind(kind_str)
        except ValueError:
            kind_enum = models.CitationKind.REFERS

        async with session_scope() as s:
            try:
                s.add(
                    models.CitationEdge(
                        src_pasal_id=pasal.id,
                        dst_pasal_id=dst_id,
                        kind=kind_enum,
                    )
                )
                await s.flush()
                stats.edges_inserted += 1
            except IntegrityError:
                # UniqueConstraint(src, dst, kind) — already present.
                await s.rollback()
                stats.edges_already_present += 1
            except Exception as e:  # noqa: BLE001
                _log.warning("citation_backfill: insert failed: %s", e)
                await s.rollback()

    return stats
