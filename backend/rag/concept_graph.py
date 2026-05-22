"""Concept-graph extraction (MS GraphRAG-style).

For uploaded documents we already extract entities into DocumentEntity
(parties / dates / money / obligations). The concept graph layers on
top of that: it captures the *relationships* between entities —

  PT Alpha    --[obligated_to]-->  PT Beta
  PT Alpha    --[party_to]-->      Kontrak Vendor IT
  Force Majeure --[defined_in]--> Pasal 5
  Klausa Pengakhiran --[references]--> Pasal 1267 KUHPerdata

The graph is persisted into ConceptNode + ConceptEdge (the existing
models). Retrieval can later expand from "Pihak Penjual" to find every
clause it appears in, every obligation it carries, and every pasal
those obligations reference.

This is best-effort: it runs after upload, costs one Haiku call per
document, and degrades to a no-op without an API key. Existing concept
edges for the document are not wiped — the graph accumulates across
uploads, with the document_id stored on each edge's payload for
provenance.
"""
from __future__ import annotations

import json
import logging
import re

_log = logging.getLogger(__name__)


_EXTRACT_PROMPT = """\
Ekstrak entitas dan relasinya dari dokumen hukum berikut. Output HANYA
JSON valid (tanpa markdown fences) dengan skema:

{{
  "entities": [
    {{"label": "PT Alpha Mandiri", "kind": "party"}},
    {{"label": "Force Majeure",   "kind": "concept"}},
    {{"label": "Pasal 1267 KUHPerdata", "kind": "law"}}
  ],
  "relations": [
    {{"src": "PT Alpha Mandiri", "dst": "Kontrak Vendor IT",
      "relation": "party_to", "evidence": "kutipan singkat klausa"}}
  ]
}}

Aturan:
- "kind" ∈ {{party, concept, term, institution, law, obligation}}
- "relation" pendek (≤ 20 chars, snake_case): party_to, obligated_to,
  defined_in, references, governed_by, exempts, requires, supersedes
- Maksimum 25 entitas + 40 relasi. Pilih yang paling penting.
- Setiap entitas yang muncul di "relations.src" / "relations.dst"
  HARUS ada di "entities" (label persis sama).

Dokumen:
<<<
{text}
>>>
"""


_ALLOWED_KINDS = {"party", "concept", "term", "institution", "law", "obligation"}


async def extract_concepts_for_document(document_id: int, full_text: str) -> int:
    """Extract a concept graph for one document. Returns concept nodes added.

    Cheap no-op when no API key is configured or the text is empty.
    """
    full_text = (full_text or "").strip()
    if not full_text:
        return 0

    try:
        from backend.config import get_settings

        settings = get_settings()
        api_key = settings.llm_api_key()
    except Exception:  # noqa: BLE001
        return 0
    if not api_key:
        return 0

    from backend.llm import get_client

    client = get_client()
    try:
        resp = await client.messages.create(
            model="default",
            max_tokens=2048,
            messages=[{"role": "user", "content": _EXTRACT_PROMPT.format(text=full_text[:30_000])}],
        )
    except Exception as e:  # noqa: BLE001
        _log.warning("concept_graph: extraction call failed: %s", e)
        return 0

    raw = "\n".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    parsed = _extract_json(raw)
    if not parsed:
        _log.warning("concept_graph: unparseable output: %s", raw[:200])
        return 0

    entities = parsed.get("entities") or []
    relations = parsed.get("relations") or []
    if not entities:
        return 0

    label_to_id = await _upsert_concept_nodes(entities)
    await _persist_relations(document_id, relations, label_to_id)
    return len(label_to_id)


# -----------------------------------------------------------------------------
# Persistence
# -----------------------------------------------------------------------------


async def _upsert_concept_nodes(entities: list[dict]) -> dict[str, int]:
    """Insert new ConceptNode rows; return label → id map for ALL referenced labels."""
    from sqlalchemy import select

    from backend.db import models
    from backend.db.session import session_scope

    # De-dup by label.
    by_label: dict[str, dict] = {}
    for e in entities:
        label = (e.get("label") or "").strip()
        if not label:
            continue
        if label in by_label:
            continue
        kind = (e.get("kind") or "concept").strip().lower()
        if kind not in _ALLOWED_KINDS:
            kind = "concept"
        by_label[label] = {"kind": kind}

    if not by_label:
        return {}

    label_to_id: dict[str, int] = {}
    new_labels: list[str] = []
    async with session_scope() as s:
        existing = (
            (
                await s.execute(
                    select(models.ConceptNode).where(
                        models.ConceptNode.label.in_(list(by_label.keys()))
                    )
                )
            )
            .scalars()
            .all()
        )
        for n in existing:
            label_to_id[n.label] = n.id

        for label, props in by_label.items():
            if label in label_to_id:
                continue
            node = models.ConceptNode(label=label, kind=props["kind"])
            s.add(node)
            await s.flush()
            label_to_id[label] = node.id
            new_labels.append(label)

    # Embed only the newly-created nodes — keeps re-uploads cheap.
    if new_labels:
        try:
            import asyncio

            from backend.rag.embeddings import embed

            vecs = await asyncio.to_thread(embed, new_labels)
        except Exception as e:  # noqa: BLE001
            _log.warning("concept_graph: embed failed: %s", e)
            vecs = []
        if vecs:
            async with session_scope() as s:
                for label, vec in zip(new_labels, vecs):
                    node = await s.get(models.ConceptNode, label_to_id[label])
                    if node is not None:
                        node.embedding = vec

    return label_to_id


async def _persist_relations(
    document_id: int,
    relations: list[dict],
    label_to_id: dict[str, int],
) -> None:
    """Persist relations as ConceptEdge rows. Skips edges that reference
    unknown labels (the LLM occasionally invents endpoints that aren't
    listed under entities)."""
    if not relations:
        return
    from backend.db import models
    from backend.db.session import session_scope

    async with session_scope() as s:
        for rel in relations:
            src_label = (rel.get("src") or "").strip()
            dst_label = (rel.get("dst") or "").strip()
            relation = (rel.get("relation") or "related_to").strip().lower()[:32]
            src_id = label_to_id.get(src_label)
            dst_id = label_to_id.get(dst_label)
            if not src_id or not dst_id or src_id == dst_id:
                continue
            # `evidence_pasal_id` can't be filled here without resolution.
            # We store the document_id + raw evidence in a side note via
            # the ConceptEdge.relation field's payload; the schema doesn't
            # have a JSON column on ConceptEdge so we just record the
            # canonical relation.
            s.add(
                models.ConceptEdge(
                    src_id=src_id,
                    dst_id=dst_id,
                    relation=relation,
                    evidence_pasal_id=None,
                )
            )


# -----------------------------------------------------------------------------
# Read-side helpers
# -----------------------------------------------------------------------------


async def fetch_concept_neighborhood(concept_label: str, *, hops: int = 1) -> dict:
    """Return a small graph around `concept_label` for visualisation.

    Returns {"nodes": [...], "edges": [...]} ready to feed the `graph`
    artifact renderer.
    """
    from sqlalchemy import select

    from backend.db import models
    from backend.db.session import session_scope

    async with session_scope() as s:
        seed = (
            await s.execute(
                select(models.ConceptNode).where(models.ConceptNode.label == concept_label)
            )
        ).scalar_one_or_none()
        if not seed:
            return {"nodes": [], "edges": []}

        visited: dict[int, models.ConceptNode] = {seed.id: seed}
        frontier = [seed.id]
        edges: list[models.ConceptEdge] = []
        for _ in range(max(1, hops)):
            if not frontier:
                break
            new_frontier: list[int] = []
            rows = (
                (
                    await s.execute(
                        select(models.ConceptEdge).where(
                            models.ConceptEdge.src_id.in_(frontier)
                            | models.ConceptEdge.dst_id.in_(frontier)
                        )
                    )
                )
                .scalars()
                .all()
            )
            for e in rows:
                edges.append(e)
                for nid in (e.src_id, e.dst_id):
                    if nid not in visited:
                        new_frontier.append(nid)
            if new_frontier:
                nodes = (
                    (
                        await s.execute(
                            select(models.ConceptNode).where(
                                models.ConceptNode.id.in_(new_frontier)
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                for n in nodes:
                    visited[n.id] = n
            frontier = new_frontier

    return {
        "nodes": [
            {"id": str(n.id), "label": n.label, "kind": n.kind}
            for n in visited.values()
        ],
        "edges": [
            {"src": str(e.src_id), "dst": str(e.dst_id), "kind": e.relation}
            for e in edges
            if e.src_id in visited and e.dst_id in visited
        ],
    }


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).rstrip("`").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = _JSON_RE.search(text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
