"""RAPTOR — Recursive Abstractive Processing for Tree-Organised Retrieval.

We build a summary tree over the corpus so retrieval can match against
high-level abstractions (Bab / Bagian / Peraturan summaries) and drill
down into precise pasal text. This catches two failure modes of flat
retrieval:

  - Broad queries ("hak pekerja PKWT") get drowned by hundreds of
    near-duplicate pasal — a Bab-level summary surfaces the right
    Bab and then we descend.
  - Aggregate queries ("ringkas seluruh kewajiban di matter ini")
    have no single leaf that answers them — the document-level
    summary does.

Two builders:
  - `build_corpus_tree()` — walks the peraturan corpus
    (Pasal → Bab → Peraturan; "Topic" level reserved for Phase 6+).
  - `build_document_tree(document_id)` — walks an uploaded document's
    DocumentOutline + chunks (Chunk → Section → Document).

Both are idempotent: existing RaptorNode rows for the same source
are wiped first. Both fall back to deterministic extractive summaries
when no API key is available — the tree still builds, just with less
abstract summaries.

Retrieval helpers live alongside (`search_branches`, `descend`).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

_log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Retrieval side
# -----------------------------------------------------------------------------


async def search_branches(qvec: list[float], k: int = 5, level_min: int = 1) -> list[dict]:
    """Top-k branch nodes (level ≥ level_min) by cosine to qvec."""
    from sqlalchemy import text

    from backend.db.session import session_scope

    sql = text(
        """
        SELECT id, level, parent_id, title, summary,
               1 - (embedding <=> CAST(:qvec AS vector)) AS score
        FROM raptor_node
        WHERE embedding IS NOT NULL AND level >= :level_min
        ORDER BY embedding <=> CAST(:qvec AS vector)
        LIMIT :k
        """
    )
    async with session_scope() as s:
        rows = (await s.execute(sql, {"qvec": qvec, "k": k, "level_min": level_min})).all()
    return [
        {
            "id": r.id,
            "level": r.level,
            "parent_id": r.parent_id,
            "title": r.title,
            "summary": r.summary,
            "score": float(r.score),
        }
        for r in rows
    ]


async def descend(node_id: int, *, qvec: list[float] | None = None, k: int = 5) -> list[dict]:
    """Return children of `node_id`, ordered by relevance to qvec if given."""
    from sqlalchemy import text

    from backend.db.session import session_scope

    if qvec is None:
        sql = text(
            """
            SELECT id, level, title, summary, 0::float AS score
            FROM raptor_node WHERE parent_id = :pid ORDER BY id
            """
        )
        params: dict = {"pid": node_id}
    else:
        sql = text(
            """
            SELECT id, level, title, summary,
                   1 - (embedding <=> CAST(:qvec AS vector)) AS score
            FROM raptor_node
            WHERE parent_id = :pid AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:qvec AS vector)
            LIMIT :k
            """
        )
        params = {"pid": node_id, "qvec": qvec, "k": k}
    async with session_scope() as s:
        rows = (await s.execute(sql, params)).all()
    return [
        {
            "id": r.id,
            "level": r.level,
            "title": r.title,
            "summary": r.summary,
            "score": float(r.score or 0.0),
        }
        for r in rows
    ]


# -----------------------------------------------------------------------------
# Build
# -----------------------------------------------------------------------------


@dataclass(slots=True)
class BuildResult:
    nodes_inserted: int
    levels_built: list[int]
    skipped_missing_summary: int = 0


async def build_corpus_tree(
    *,
    peraturan_ids: list[int] | None = None,
    max_concurrent_summaries: int = 4,
) -> BuildResult:
    """Build a summary tree over the peraturan corpus.

    If `peraturan_ids` is None we walk every peraturan row. Existing
    raptor_node rows for the same source (via payload.peraturan_id)
    are wiped first.
    """
    from sqlalchemy import select

    from backend.db import models
    from backend.db.session import session_scope

    async with session_scope() as s:
        q = select(models.Peraturan)
        if peraturan_ids:
            q = q.where(models.Peraturan.id.in_(peraturan_ids))
        per_rows = (await s.execute(q)).scalars().all()

    inserted = 0
    levels: set[int] = set()
    skipped = 0
    for per in per_rows:
        n, lvls, sk = await _build_for_peraturan(per, max_concurrent_summaries)
        inserted += n
        levels |= lvls
        skipped += sk
    return BuildResult(
        nodes_inserted=inserted, levels_built=sorted(levels), skipped_missing_summary=skipped
    )


async def _build_for_peraturan(per, max_concurrent: int) -> tuple[int, set[int], int]:
    from sqlalchemy import select, text

    from backend.db import models
    from backend.db.session import session_scope

    async with session_scope() as s:
        await s.execute(
            text("DELETE FROM raptor_node WHERE payload ->> 'peraturan_id' = :pid"),
            {"pid": str(per.id)},
        )
        bab_rows = (
            (
                await s.execute(
                    select(models.Bab)
                    .where(models.Bab.peraturan_id == per.id)
                    .order_by(models.Bab.id)
                )
            )
            .scalars()
            .all()
        )
        pasal_rows = (
            (
                await s.execute(
                    select(models.Pasal)
                    .where(models.Pasal.peraturan_id == per.id)
                    .order_by(models.Pasal.id)
                )
            )
            .scalars()
            .all()
        )

    # Group pasal under their bab.
    pasal_by_bab: dict[int | None, list] = {}
    for p in pasal_rows:
        pasal_by_bab.setdefault(p.bab_id, []).append(p)

    sem = asyncio.Semaphore(max_concurrent)
    bab_nodes: dict[int, dict] = {}
    bab_tasks = []
    for b in bab_rows:
        children = pasal_by_bab.get(b.id, [])
        bab_title = f"BAB {b.nomor}" + (f" — {b.judul}" if b.judul else "")
        basis = "\n\n".join(f"Pasal {p.nomor}: {(p.teks or '')[:500]}" for p in children)
        node = {
            "level": 1,
            "title": bab_title,
            "summary": "",
            "payload": {"peraturan_id": str(per.id), "bab_id": b.id, "kind": "bab"},
        }
        bab_nodes[b.id] = node
        bab_tasks.append(_summarise(sem, bab_title, basis, node))
    if bab_tasks:
        await asyncio.gather(*bab_tasks)

    # Peraturan-level summary.
    per_title = _peraturan_label(per)
    per_basis = (
        "\n\n".join(f"{n['title']}: {n['summary']}" for n in bab_nodes.values() if n["summary"])
        or "\n\n".join(f"Pasal {p.nomor}: {(p.teks or '')[:300]}" for p in pasal_rows)
    )
    per_node = {
        "level": 3,
        "title": per_title,
        "summary": "",
        "payload": {"peraturan_id": str(per.id), "kind": "peraturan"},
    }
    await _summarise(sem, per_title, per_basis, per_node)

    inserted = 0
    levels: set[int] = set()
    skipped = 0
    # session_scope + models already imported at function entry
    async with session_scope() as s:
        # Peraturan node
        per_row = models.RaptorNode(
            level=per_node["level"],
            title=per_node["title"],
            summary=per_node["summary"] or per_title,
            payload=per_node["payload"],
        )
        s.add(per_row)
        await s.flush()
        if per_node["summary"]:
            per_row.embedding = (await _embed_async([per_node["summary"]]))[0]
        else:
            skipped += 1
        levels.add(per_node["level"])
        inserted += 1

        # Bab nodes
        for b in bab_rows:
            n = bab_nodes[b.id]
            row = models.RaptorNode(
                level=n["level"],
                parent_id=per_row.id,
                title=n["title"],
                summary=n["summary"] or n["title"],
                payload=n["payload"],
            )
            s.add(row)
            await s.flush()
            if n["summary"]:
                row.embedding = (await _embed_async([n["summary"]]))[0]
            else:
                skipped += 1
            levels.add(n["level"])
            n["db_id"] = row.id
            inserted += 1

        # Pasal leaves
        for p in pasal_rows:
            parent_db_id = bab_nodes[p.bab_id]["db_id"] if p.bab_id in bab_nodes else per_row.id
            row = models.RaptorNode(
                level=0,
                parent_id=parent_db_id,
                title=f"Pasal {p.nomor}",
                summary=(p.teks or "")[:1200] or f"Pasal {p.nomor}",
                payload={"peraturan_id": str(per.id), "pasal_id": p.id, "kind": "pasal"},
            )
            if p.embedding is not None:
                row.embedding = p.embedding
            elif p.teks:
                row.embedding = (await _embed_async([p.teks[:1200]]))[0]
            s.add(row)
            levels.add(0)
            inserted += 1

    return inserted, levels, skipped


async def build_document_tree(document_id: int, *, max_concurrent: int = 4) -> BuildResult:
    """Build a RAPTOR tree over a single uploaded document.

    Shape: Document (level 3) → outline section nodes (level 1-2) →
    chunks (level 0).
    """
    from sqlalchemy import select, text

    from backend.db import models
    from backend.db.session import session_scope

    async with session_scope() as s:
        doc = await s.get(models.Document, document_id)
        if not doc:
            return BuildResult(0, [])

        outline_rows = (
            (
                await s.execute(
                    select(models.DocumentOutline)
                    .where(models.DocumentOutline.document_id == document_id)
                    .order_by(models.DocumentOutline.level, models.DocumentOutline.ordinal)
                )
            )
            .scalars()
            .all()
        )
        chunks = (
            (
                await s.execute(
                    select(models.DocumentChunk)
                    .where(models.DocumentChunk.document_id == document_id)
                    .order_by(models.DocumentChunk.ordinal)
                )
            )
            .scalars()
            .all()
        )

        await s.execute(
            text("DELETE FROM raptor_node WHERE payload ->> 'document_id' = :did"),
            {"did": str(document_id)},
        )

    if not chunks:
        return BuildResult(0, [])

    chunks_by_outline: dict[int | None, list] = {}
    for c in chunks:
        chunks_by_outline.setdefault(c.outline_id, []).append(c)

    sem = asyncio.Semaphore(max_concurrent)
    outline_nodes: dict[int, dict] = {}
    outline_tasks = []
    for r in outline_rows:
        cs = chunks_by_outline.get(r.id) or []
        if not cs:
            continue
        basis = "\n\n".join((c.text or "")[:400] for c in cs)
        node = {
            "outline": r,
            "level_raptor": _outline_level_to_raptor(r.level),
            "summary": "",
            "payload": {
                "document_id": str(document_id),
                "outline_id": r.id,
                "kind": r.kind,
            },
        }
        outline_nodes[r.id] = node
        outline_tasks.append(_summarise(sem, r.title or r.kind, basis, node))
    if outline_tasks:
        await asyncio.gather(*outline_tasks)

    # Document-level summary.
    doc_basis = "\n\n".join(n["summary"] for n in outline_nodes.values() if n["summary"]) or "\n\n".join(
        (c.text or "")[:300] for c in chunks[:20]
    )
    doc_node = {
        "level": 3,
        "title": doc.title,
        "summary": "",
        "payload": {"document_id": str(document_id), "kind": "document"},
    }
    await _summarise(sem, doc.title, doc_basis, doc_node)

    from backend.db import models  # noqa: F811 — re-import within scope
    from backend.db.session import session_scope  # noqa: F811

    inserted = 0
    levels: set[int] = set()
    async with session_scope() as s:
        doc_row = models.RaptorNode(
            level=doc_node["level"],
            title=doc_node["title"],
            summary=doc_node["summary"] or doc.title,
            payload=doc_node["payload"],
        )
        s.add(doc_row)
        await s.flush()
        if doc_node["summary"]:
            doc_row.embedding = (await _embed_async([doc_node["summary"]]))[0]
        inserted += 1
        levels.add(doc_node["level"])

        sorted_outlines = sorted(outline_nodes.values(), key=lambda n: n["outline"].level)
        outline_db_ids: dict[int, int] = {}
        for n in sorted_outlines:
            r = n["outline"]
            parent_db_id = outline_db_ids.get(r.parent_id) if r.parent_id else doc_row.id
            row = models.RaptorNode(
                level=n["level_raptor"],
                parent_id=parent_db_id,
                title=r.title or r.kind,
                summary=n["summary"] or (r.title or r.kind),
                payload=n["payload"],
            )
            if n["summary"]:
                row.embedding = (await _embed_async([n["summary"]]))[0]
            s.add(row)
            await s.flush()
            outline_db_ids[r.id] = row.id
            levels.add(n["level_raptor"])
            inserted += 1

    return BuildResult(nodes_inserted=inserted, levels_built=sorted(levels))


# -----------------------------------------------------------------------------
# Internals
# -----------------------------------------------------------------------------


def _outline_level_to_raptor(outline_level: int) -> int:
    """Map outline depth → RAPTOR level. RAPTOR levels: 0=leaf, 1=section, 2=bab, 3=doc."""
    if outline_level <= 1:
        return 2
    if outline_level == 2:
        return 1
    return 0


def _peraturan_label(per) -> str:
    j = per.jenis.value if hasattr(per.jenis, "value") else per.jenis
    if j in {"KUHP", "KUHPerdata", "KUHAP", "UUD"}:
        return f"{j}" + (f" — {per.judul}" if per.judul else "")
    parts = [j]
    if per.nomor:
        parts.append(per.nomor)
    if per.tahun:
        parts.append(str(per.tahun))
    return " ".join(parts)


async def _embed_async(texts: list[str]) -> list[list[float]]:
    from backend.rag.embeddings import embed

    return await asyncio.to_thread(embed, texts)


_SUMMARY_PROMPT = """\
Ringkas teks hukum berikut menjadi 2-3 kalimat dalam Bahasa Indonesia.
Sebut topik utama, lingkup yang diatur, dan istilah-istilah kunci.
Tanpa preamble, tanpa kutipan pasal verbatim.

Judul: {title}

Teks:
{text}
"""


async def _summarise(sem: asyncio.Semaphore, title: str, basis: str, target: dict) -> None:
    basis = (basis or "").strip()
    if not basis:
        target["summary"] = ""
        return

    try:
        from backend.config import get_settings

        api_key = get_settings().llm_api_key()
    except Exception:  # noqa: BLE001
        api_key = None

    if not api_key:
        target["summary"] = basis[:220].strip()
        return

    async with sem:
        try:
            from backend.llm import get_client

            client = get_client()
            resp = await client.messages.create(
                model="fast",
                max_tokens=220,
                messages=[
                    {
                        "role": "user",
                        "content": _SUMMARY_PROMPT.format(title=title, text=basis[:6000]),
                    }
                ],
            )
            parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
            target["summary"] = "\n".join(parts).strip() or basis[:220].strip()
        except Exception as e:  # noqa: BLE001
            _log.warning("raptor.summarise: %s", e)
            target["summary"] = basis[:220].strip()
