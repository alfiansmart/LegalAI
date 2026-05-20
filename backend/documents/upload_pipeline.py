"""End-to-end ingest pipeline for a user-uploaded contract or legal text.

Glues together: text extraction → structure parsing → structure-aware
chunking → defined-term extraction → context-augmented embeddings →
citation backfill. Each step is its own module so they're individually
testable.

This runs synchronously inside the request for now. When ingest time
becomes a UX concern we'll wrap it in a Celery task; the function
signature is already async-friendly.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select

from backend.db import models
from backend.db.session import session_scope
from backend.documents import extract, service as doc_service
from backend.rag import citation as citation_mod, contextual, definitions, embeddings, temporal
from backend.rag.chunker import Chunk, chunk_document
from backend.rag.doc_structure import OutlineNode

_log = logging.getLogger(__name__)


@dataclass(slots=True)
class IngestResult:
    document_id: int
    chunks_inserted: int
    outline_nodes: int
    terms_extracted: int
    citations_inferred: int
    text_chars: int


async def ingest_uploaded_document(
    *,
    filename: str,
    data: bytes,
    user_id: str | None = None,
    matter_id: int | None = None,
    title: str | None = None,
    kind: str = "kontrak_upload",
) -> IngestResult:
    """Ingest a single uploaded file. Returns counts for the success toast."""
    text = extract.extract(filename, data)
    if not text or not text.strip():
        raise ValueError(f"empty extraction for {filename!r}")

    document_id = await doc_service.create_draft(
        user_id=user_id,
        title=title or filename,
        kind=kind,
        content=text,
        matter_id=matter_id,
        source_filename=filename,
    )

    # 1) parse + chunk
    outline_root, chunks = chunk_document(text)

    # 2) persist outline
    outline_nodes = await _persist_outline(document_id, outline_root)

    # 3) defined terms
    terms = definitions.extract_definitions(text, outline=outline_root)
    if terms:
        await _persist_terms(document_id, terms)

    # 4) contextual augmentation + embedding
    if chunks:
        blurbs = await contextual.contextualise_chunks(
            text,
            [c.text for c in chunks],
            breadcrumbs=[c.breadcrumb for c in chunks],
            parent_summaries=[c.parent_summary for c in chunks],
        )
        augmented = [contextual.augment_for_embedding(c.text, b) for c, b in zip(chunks, blurbs)]
        vectors = embeddings.embed(augmented)
        outline_leaf_ids = await _outline_leaf_ids_by_path(document_id, outline_root)
        await _persist_chunks(
            document_id=document_id,
            matter_id=matter_id,
            chunks=chunks,
            augmented=augmented,
            vectors=vectors,
            outline_leaf_ids=outline_leaf_ids,
        )

    # 5) citation backfill
    cits = await _backfill_citations(document_id, text)

    return IngestResult(
        document_id=document_id,
        chunks_inserted=len(chunks),
        outline_nodes=outline_nodes,
        terms_extracted=len(terms),
        citations_inferred=cits,
        text_chars=len(text),
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


async def _persist_outline(document_id: int, root: OutlineNode) -> int:
    """Persist outline as DocumentOutline rows. Returns number of rows inserted.

    We persist a flat list with `parent_id` linking back to the parent row.
    A second pass fills in parent IDs once all rows have a primary key.
    """
    inserted = 0
    async with session_scope() as s:
        # Map id(OutlineNode) -> DocumentOutline DB id
        id_map: dict[int, int] = {}

        # BFS-style traversal so parents are inserted before children.
        queue: list[OutlineNode] = list(root.children)
        flat: list[OutlineNode] = []
        while queue:
            n = queue.pop(0)
            flat.append(n)
            queue.extend(n.children)

        for n in flat:
            row = models.DocumentOutline(
                document_id=document_id,
                parent_id=None,  # filled below
                level=n.level,
                ordinal=n.ordinal,
                kind=n.kind,
                title=n.title,
                span_start=n.span_start,
                span_end=n.span_end,
            )
            s.add(row)
            await s.flush()
            id_map[id(n)] = row.id
            if n.parent is not None and n.parent.kind != "root":
                parent_db_id = id_map.get(id(n.parent))
                if parent_db_id:
                    row.parent_id = parent_db_id
            inserted += 1
    return inserted


async def _outline_leaf_ids_by_path(
    document_id: int, root: OutlineNode
) -> dict[tuple[str, ...], int]:
    """Map a chunk's outline path -> the DB id of its leaf outline node.

    Path key = tuple of (kind, ordinal) pairs from root to leaf, encoded
    as strings.
    """
    out: dict[tuple[str, ...], int] = {}
    async with session_scope() as s:
        rows = (
            (
                await s.execute(
                    select(models.DocumentOutline).where(
                        models.DocumentOutline.document_id == document_id
                    )
                )
            )
            .scalars()
            .all()
        )
        by_id: dict[int, models.DocumentOutline] = {r.id: r for r in rows}

        def path_of(r: models.DocumentOutline) -> tuple[str, ...]:
            parts: list[str] = []
            cur: models.DocumentOutline | None = r
            while cur is not None:
                parts.append(f"{cur.kind}:{cur.ordinal}")
                cur = by_id.get(cur.parent_id) if cur.parent_id else None
            return tuple(reversed(parts))

        for r in rows:
            out[path_of(r)] = r.id
    return out


async def _persist_chunks(
    *,
    document_id: int,
    matter_id: int | None,
    chunks: list[Chunk],
    augmented: list[str],
    vectors: list[list[float]],
    outline_leaf_ids: dict[tuple[str, ...], int],
) -> None:
    async with session_scope() as s:
        for ch, aug, vec in zip(chunks, augmented, vectors):
            path_key = tuple(f"{n.kind}:{n.ordinal}" for n in ch.outline_path)
            outline_id = outline_leaf_ids.get(path_key)
            s.add(
                models.DocumentChunk(
                    document_id=document_id,
                    matter_id=matter_id,
                    outline_id=outline_id,
                    ordinal=ch.ordinal,
                    text=ch.text,
                    contextual_text=aug,
                    breadcrumb=ch.breadcrumb,
                    parent_summary=ch.parent_summary,
                    token_count=ch.token_count,
                    embedding=vec,
                )
            )


async def _persist_terms(document_id: int, terms: list) -> None:
    async with session_scope() as s:
        for t in terms:
            s.add(
                models.DocumentTerm(
                    document_id=document_id,
                    term=t.term,
                    definition=t.definition,
                    span_start=t.span_start,
                    span_end=t.span_end,
                )
            )


async def _backfill_citations(document_id: int, text: str) -> int:
    refs = citation_mod.parse_citations(text)
    if not refs:
        return 0
    inserted = 0
    async with session_scope() as s:
        seen: set[tuple[int, str]] = set()
        for ref in refs:
            if not ref.jenis or not ref.pasal:
                continue
            resolved = await temporal.pasal_as_of(
                peraturan_jenis=ref.jenis,
                peraturan_nomor=ref.nomor,
                peraturan_tahun=ref.tahun,
                pasal_nomor=ref.pasal,
                ayat_nomor=ref.ayat,
                huruf=ref.huruf,
            )
            if not resolved or not resolved.get("id"):
                continue
            key = (resolved["id"], "refers")
            if key in seen:
                continue
            seen.add(key)
            s.add(
                models.DocumentCitation(
                    document_id=document_id,
                    pasal_id=resolved["id"],
                    kind=models.CitationKind.REFERS,
                    raw_text=ref.raw,
                )
            )
            inserted += 1
    return inserted
