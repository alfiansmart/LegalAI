"""Propose a rewrite of an existing document range as a Suggestion.

Two modes:
  - scoped: caller passes range_start + range_end → AI only rewrites
    that span; the surrounding text stays put.
  - whole-doc: range_start/end omitted → AI proposes one Suggestion
    covering the entire latest version.

The output is one Suggestion row per discrete change the AI wants to
make (the LLM is allowed to return multiple if the instruction implies
several disjoint edits). Each is created with source="ai", status=
"pending" so the lawyer can accept/reject from the editor via the
existing /suggestions/{id}/accept|reject endpoints.

The skill also returns a `diff` artifact so the AI's reply (rendered
in chat or in the side panel) shows the proposed change inline before
the lawyer drills into the Suggestion list.
"""
from __future__ import annotations

import json
import re


_REVISE_PROMPT = """\
Anda adalah penyusun perjanjian hukum Indonesia. Pengguna meminta revisi
pada dokumen berikut.

Instruksi pengguna: \"\"\"{instruction}\"\"\"

Dokumen lengkap:
<<<
{full_doc}
>>>

{scope_block}

Tugas Anda:
- Identifikasi satu atau beberapa span teks yang perlu diubah.
- Untuk setiap span, sajikan teks lama (verbatim — harus persis ada di
  dokumen) dan teks baru yang menggantikannya.
- Tulis alasan singkat (1–2 kalimat) per perubahan.

Kembalikan HANYA JSON valid:

{{
  "changes": [
    {{
      "base_text": "<teks lama, verbatim>",
      "proposed_text": "<teks baru>",
      "rationale": "<alasan>"
    }}
  ]
}}

Kalau tidak ada yang perlu diubah, kembalikan {{"changes": []}}.
"""


_SCOPE_TEMPLATE = """\
Fokus revisi pada span ini saja (offset {start}–{end}):
\"\"\"
{snippet}
\"\"\"
"""


async def execute(agent=None, args: dict | None = None) -> dict:
    from sqlalchemy import select

    from backend.agents import artifacts as A
    from backend.llm import get_client
    from backend.config import get_settings
    from backend.db import models
    from backend.db.session import session_scope
    from backend.documents import service as doc_service

    args = args or {}
    document_id = args.get("document_id")
    instruction = (args.get("instruction") or "").strip()
    if not document_id or not instruction:
        return {"status": "error", "message": "need document_id + instruction"}
    document_id = int(document_id)
    range_start = args.get("range_start")
    range_end = args.get("range_end")

    full_doc = await doc_service.latest_content(document_id)
    if full_doc is None:
        return {"status": "error", "message": f"document {document_id} not found"}

    scope_block = ""
    if range_start is not None and range_end is not None:
        try:
            range_start = max(0, int(range_start))
            range_end = min(len(full_doc), int(range_end))
        except (TypeError, ValueError):
            return {"status": "error", "message": "range_start/range_end must be ints"}
        if range_end <= range_start:
            return {"status": "error", "message": "range_end must be > range_start"}
        snippet = full_doc[range_start:range_end]
        scope_block = _SCOPE_TEMPLATE.format(
            start=range_start, end=range_end, snippet=snippet[:2000]
        )

    settings = get_settings()
    if not settings.llm_api_key():
        return {"status": "error", "message": "LLM provider API key not configured"}

    client = get_client()
    resp = await client.messages.create(
        model="default",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": _REVISE_PROMPT.format(
                    instruction=instruction,
                    full_doc=full_doc[:30_000],
                    scope_block=scope_block,
                ),
            }
        ],
    )
    raw = "\n".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
    parsed = _extract_json(raw) or {}
    changes = parsed.get("changes") or []
    if not changes:
        return {"status": "ok", "suggestions": [], "message": "AI tidak menemukan revisi yang perlu diusulkan."}

    # Locate each base_text in the document to get char offsets.
    persisted: list[dict] = []
    session_id = getattr(agent, "session_id", None)
    async with session_scope() as s:
        for c in changes:
            base_text = (c.get("base_text") or "").strip()
            proposed_text = (c.get("proposed_text") or "").strip()
            if not base_text or not proposed_text:
                continue
            idx = full_doc.find(base_text)
            if idx < 0:
                # Try a normalised whitespace match.
                idx = _fuzzy_find(full_doc, base_text)
            if idx < 0:
                # Skip silently — the LLM hallucinated text that isn't there.
                continue
            sug = models.Suggestion(
                document_id=document_id,
                user_id=session_id,
                source="ai",
                range_start=idx,
                range_end=idx + len(base_text),
                base_text=base_text,
                proposed_text=proposed_text,
                rationale=c.get("rationale"),
            )
            s.add(sug)
            await s.flush()
            persisted.append(
                {
                    "id": sug.id,
                    "range_start": sug.range_start,
                    "range_end": sug.range_end,
                    "base_text": base_text,
                    "proposed_text": proposed_text,
                    "rationale": c.get("rationale"),
                }
            )

    # Build a synthetic "diff" artifact showing the first change for
    # at-a-glance review. The full list is in `suggestions`; the lawyer
    # opens the side panel to walk through them.
    artifacts: list[dict] = []
    if persisted:
        first = persisted[0]
        artifacts.append(
            A.diff(
                f"Usulan revisi ({len(persisted)} change{'s' if len(persisted) > 1 else ''})",
                first["base_text"],
                first["proposed_text"],
                annotations=[
                    {"line": 1, "message": (first.get("rationale") or "")[:200]}
                ],
            )
        )
        artifacts.append(
            A.table(
                "Usulan revisi",
                ["#", "Sebelum (≤80c)", "Sesudah (≤80c)", "Alasan"],
                [
                    [
                        i + 1,
                        (p["base_text"] or "")[:80],
                        (p["proposed_text"] or "")[:80],
                        (p.get("rationale") or "")[:120],
                    ]
                    for i, p in enumerate(persisted)
                ],
            )
        )

    return {
        "status": "ok",
        "suggestions": persisted,
        "message": f"{len(persisted)} usulan revisi siap ditinjau.",
        "artifacts": artifacts,
    }


def _fuzzy_find(haystack: str, needle: str) -> int:
    """Find needle in haystack ignoring repeated whitespace.

    Indonesian peraturan often have indented sub-clauses and line wraps
    that make a verbatim find() miss the model's quoted text. We split
    the needle on whitespace and rejoin with a flexible `\\s+` matcher,
    so "Setiap pekerja berhak" matches "Setiap   pekerja\\n  berhak"
    in the source.

    Returns the char offset in the *original* haystack, or -1.
    """
    norm = re.sub(r"\s+", " ", needle).strip()
    if not norm:
        return -1
    parts = [re.escape(p) for p in norm.split(" ") if p]
    pattern = re.compile(r"\s+".join(parts))
    m = pattern.search(haystack)
    return m.start() if m else -1


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
