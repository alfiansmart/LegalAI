"""Generate a new clause and queue it as an insert-style Suggestion.

`clause_type` accepts either a known slug (force_majeure, data_protection,
non_solicitation, arbitrase_bani, …) or free-form Bahasa Indonesia
("klausa kerahasiaan data karyawan"). The AI inspects the existing
draft so the new clause matches its tone + numbering scheme.

The insert position:
  - if `after_section` is given, we find that section heading in the
    current text and insert right before the next Pasal / end-of-doc.
  - otherwise, append before the closing block (or at end-of-doc if no
    closing block detected).

The result is a Suggestion with base_text="" (insert-style — range_end
== range_start), proposed_text = the generated clause. Accepting it
splices the clause in at that position via the existing accept flow.
"""
from __future__ import annotations

import json
import re


_CLAUSE_PROMPT = """\
Anda menyusun satu klausa tambahan untuk perjanjian Indonesia berikut.

Klausa yang diminta: \"\"\"{clause_type}\"\"\"

Konteks dokumen saat ini (untuk meniru gaya, penomoran, dan terminologi):
<<<
{context}
>>>

Tugas:
- Tulis satu Pasal baru yang konsisten dengan penomoran & gaya dokumen.
- Jika dokumen sudah berisi Pasal 1..N, klausa baru jadi "Pasal {next_number}".
- Sertakan judul Pasal, badan teks, dan sub-ayat jika perlu.
- Jangan ulang teks yang sudah ada di dokumen.

Kembalikan HANYA JSON valid:

{{
  "title": "<judul Pasal baru, mis. 'Pasal 12 — Force Majeure'>",
  "markdown": "<seluruh teks Pasal baru, mulai dari baris judul Pasal>",
  "rationale": "<satu kalimat: mengapa klausa ini penting>"
}}
"""


_PASAL_HEADING_RE = re.compile(r"^\s*Pasal\s+(\d+)", re.M)
# Closing block: detect "Ditetapkan di X pada tanggal Y" or "Pada hari ini …
# para pihak menandatangani …" markers.
_CLOSING_RE = re.compile(
    r"\b(Ditetapkan\s+di|Demikian\s+perjanjian\s+ini|PARA\s+PIHAK)\b", re.I
)


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
    clause_type = (args.get("clause_type") or "").strip()
    after_section = (args.get("after_section") or "").strip()
    if not document_id or not clause_type:
        return {"status": "error", "message": "need document_id + clause_type"}
    document_id = int(document_id)

    full_doc = await doc_service.latest_content(document_id)
    if full_doc is None:
        return {"status": "error", "message": f"document {document_id} not found"}

    next_n = _next_pasal_number(full_doc)
    insert_at = _find_insertion_offset(full_doc, after_section)

    settings = get_settings()
    if not settings.llm_api_key():
        return {"status": "error", "message": "LLM provider API key not configured"}

    client = get_client()
    # Send only a 4K window of context around the insertion point so the
    # model sees neighbouring style without paying for the whole doc.
    ctx_start = max(0, insert_at - 2000)
    ctx_end = min(len(full_doc), insert_at + 2000)
    context = full_doc[ctx_start:ctx_end]

    resp = await client.messages.create(
        model="default",
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": _CLAUSE_PROMPT.format(
                    clause_type=clause_type,
                    context=context,
                    next_number=next_n,
                ),
            }
        ],
    )
    raw = "\n".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
    parsed = _extract_json(raw) or {}
    markdown = (parsed.get("markdown") or "").strip()
    if not markdown:
        return {"status": "error", "message": "AI did not return a clause"}

    title = parsed.get("title") or f"Pasal {next_n}"
    rationale = parsed.get("rationale")

    session_id = getattr(agent, "session_id", None)
    # Insert-style suggestion: range collapses to a point, base_text empty,
    # proposed_text = clause text (with surrounding blank lines).
    proposed = "\n\n" + markdown.rstrip() + "\n\n"
    async with session_scope() as s:
        sug = models.Suggestion(
            document_id=document_id,
            user_id=session_id,
            source="ai",
            range_start=insert_at,
            range_end=insert_at,
            base_text="",
            proposed_text=proposed,
            rationale=rationale or f"Sisipkan {title}",
        )
        s.add(sug)
        await s.flush()
        sug_id = sug.id

    artifacts = [
        A.diff(
            f"Klausa baru: {title}",
            "",
            markdown,
            annotations=[{"line": 1, "message": rationale or title}],
        )
    ]

    return {
        "status": "ok",
        "suggestion_id": sug_id,
        "title": title,
        "insert_at": insert_at,
        "next_pasal_number": next_n,
        "rationale": rationale,
        "preview": markdown[:400],
        "artifacts": artifacts,
    }


def _next_pasal_number(text: str) -> int:
    nums = [int(m.group(1)) for m in _PASAL_HEADING_RE.finditer(text)]
    return (max(nums) + 1) if nums else 1


def _find_insertion_offset(text: str, after_section: str) -> int:
    """Return the char offset at which to splice the new clause."""
    if after_section:
        # Look for the section heading; insert right before the next Pasal.
        idx = text.lower().find(after_section.lower())
        if idx >= 0:
            after = text[idx:]
            next_pasal = _PASAL_HEADING_RE.search(after, pos=len(after_section))
            if next_pasal:
                return idx + next_pasal.start()
    # Default: insert before the closing block, or at end-of-doc.
    closing = _CLOSING_RE.search(text)
    if closing:
        return closing.start()
    return len(text)


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
