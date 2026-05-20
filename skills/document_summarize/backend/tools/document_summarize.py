"""Summarize a long uploaded document with structural coverage.

The trick for long documents is to use the outline tree as a coverage
checklist — we serialise the outline into the prompt and instruct the
model to produce a summary that touches every top-level section. The
final response carries:
  - text summary,
  - `tree` artifact: the document outline,
  - `table` artifact: extracted obligations.
"""
from __future__ import annotations

import json
import re

from sqlalchemy import select

from backend.agents import artifacts as A
from backend.config import get_settings
from backend.db import models
from backend.db.session import session_scope


_SUMMARIZE_PROMPT = """\
Anda adalah asisten hukum yang merangkum dokumen panjang.

Dokumen di bawah ini disertai outline strukturalnya. Pastikan ringkasan
Anda *mencakup seluruh dokumen*, bukan hanya bagian awal — gunakan
outline sebagai checklist coverage.

Outline (struktur dokumen):
{outline_md}

Dokumen lengkap:
<<<
{document_text}
>>>

Kembalikan HANYA JSON valid (tanpa fence ```) dengan skema:

{{
  "exec_summary": "3-5 kalimat ringkasan eksekutif",
  "key_clauses": [
    {{"breadcrumb": "Section 4 / Clause 4.2", "title": "Force Majeure", "excerpt": "≤200 char"}}
  ],
  "obligations": [
    {{"party": "Pihak Pertama", "obligation": "menyerahkan barang",
      "deadline": "30 hari setelah penandatanganan", "source": "Section 5.1"}}
  ]
}}
"""


async def execute(agent=None, args: dict | None = None) -> dict:
    from anthropic import AsyncAnthropic

    args = args or {}
    document_id = args.get("document_id")
    if not document_id:
        return {"status": "error", "message": "need document_id"}

    document_id = int(document_id)

    async with session_scope() as s:
        doc = await s.get(models.Document, document_id)
        if not doc:
            return {"status": "error", "message": f"document {document_id} not found"}
        title = doc.title
        versions = (
            (
                await s.execute(
                    select(models.DocumentVersion)
                    .where(models.DocumentVersion.document_id == document_id)
                    .order_by(models.DocumentVersion.version.desc())
                    .limit(1)
                )
            )
            .scalars()
            .all()
        )
        text = versions[0].content if versions else ""
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
    if not text:
        return {"status": "error", "message": "document has no content"}

    settings = get_settings()
    if not settings.anthropic_api_key:
        return {"status": "error", "message": "ANTHROPIC_API_KEY not set"}

    # Build the outline markdown checklist + a hierarchical tree for the
    # artifact in one pass.
    outline_md, tree_root = _render_outline(outline_rows, title)

    prompt = _SUMMARIZE_PROMPT.format(
        outline_md=outline_md or "(outline tidak tersedia)",
        document_text=text[:120_000],  # generous budget
    )

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    resp = await client.messages.create(
        model=settings.anthropic_model_default,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "\n".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
    parsed = _extract_json(raw) or {}
    if not parsed:
        return {"status": "error", "message": "failed to parse model output", "raw": raw[:500]}

    summary = parsed.get("exec_summary", "")
    key_clauses = parsed.get("key_clauses", [])
    obligations = parsed.get("obligations", [])

    arts: list[dict] = []
    if tree_root:
        arts.append(A.tree(f"Struktur dokumen: {title}", tree_root))
    if obligations:
        arts.append(
            A.table(
                "Kewajiban",
                ["Pihak", "Kewajiban", "Tenggat", "Sumber"],
                [
                    [
                        o.get("party", ""),
                        o.get("obligation", ""),
                        o.get("deadline", ""),
                        o.get("source", ""),
                    ]
                    for o in obligations
                ],
            )
        )

    return {
        "status": "ok",
        "summary": summary,
        "key_clauses": key_clauses,
        "obligations": obligations,
        "artifacts": arts,
    }


def _render_outline(rows, title: str) -> tuple[str, dict | None]:
    """Render the outline rows into both markdown (for the prompt) and a tree
    artifact (for the frontend)."""
    if not rows:
        return "", None
    # Build parent_id -> children map
    children: dict[int | None, list] = {}
    by_id: dict[int, object] = {}
    for r in rows:
        by_id[r.id] = r
        children.setdefault(r.parent_id, []).append(r)

    def tree_node(row) -> dict:
        kids = sorted(children.get(row.id, []), key=lambda r: (r.level, r.ordinal))
        node = {"label": row.title or row.kind.title()}
        if kids:
            node["children"] = [tree_node(k) for k in kids]
        return node

    roots = sorted(children.get(None, []), key=lambda r: (r.level, r.ordinal))
    tree_root = {"label": title, "children": [tree_node(r) for r in roots]}

    # Markdown checklist for the prompt
    lines: list[str] = []

    def md_render(row, depth: int):
        bullet = "  " * depth + "- "
        lines.append(bullet + (row.title or row.kind.title()))
        for k in sorted(children.get(row.id, []), key=lambda r: (r.level, r.ordinal)):
            md_render(k, depth + 1)

    for r in roots:
        md_render(r, 0)

    return "\n".join(lines), tree_root


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
