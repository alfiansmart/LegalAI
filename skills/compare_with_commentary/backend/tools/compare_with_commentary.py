"""Compare two documents (or one document vs a baseline template) and
annotate each non-equal hunk with AI commentary in Bahasa Indonesia.

Output:
  - hunks: structured list with base/head text + kind + AI commentary.
  - diff artifact (rendered side-by-side on the frontend).
  - table artifact summarising changes.
"""
from __future__ import annotations

import json
import re

from sqlalchemy import select

from backend.agents import artifacts as A
from backend.config import get_settings
from backend.db import models
from backend.db.session import session_scope
from backend.documents import redline, service as doc_service, templates as templates_mod


_COMMENTARY_PROMPT = """\
Berikut adalah daftar perubahan (hunks) antara dokumen baseline dan dokumen baru.
Untuk setiap hunk, tulis komentar singkat (≤ 2 kalimat) dalam Bahasa Indonesia
yang menjelaskan apa yang berubah dan mengapa itu penting secara hukum.
Tandai severity sebagai "low" | "medium" | "high" | "critical".

Kembalikan HANYA JSON valid:

{{
  "hunks": [
    {{"index": 0, "commentary": "…", "severity": "medium"}}
  ]
}}

Hunks:
{hunks_json}
"""


async def execute(agent=None, args: dict | None = None) -> dict:
    from backend.llm import get_client

    args = args or {}
    head_id = args.get("head_document_id")
    base_id = args.get("base_document_id")
    base_template_id = args.get("base_template_id")
    if not head_id:
        return {"status": "error", "message": "need head_document_id"}
    head_id = int(head_id)

    head_text = await doc_service.latest_content(head_id) or ""
    base_text = ""
    base_label = ""
    if base_id:
        base_id = int(base_id)
        base_text = await doc_service.latest_content(base_id) or ""
        async with session_scope() as s:
            d = await s.get(models.Document, base_id)
            base_label = d.title if d else f"doc {base_id}"
    elif base_template_id:
        tpl = templates_mod.get_template(base_template_id)
        if tpl:
            base_text = tpl.body
            base_label = tpl.title

    if not head_text or not base_text:
        return {"status": "error", "message": "missing base or head text"}

    hunks_raw = redline.diff(base_text, head_text)
    # Keep only non-equal hunks for commentary (equal ones are unchanged).
    interesting = [
        {"index": i, "kind": h.kind, "base": h.base, "head": h.head}
        for i, h in enumerate(hunks_raw)
        if h.kind != "equal"
    ]

    settings = get_settings()
    commentary: dict[int, dict] = {}
    if settings.llm_api_key() and interesting:
        client = get_client()
        # Truncate each hunk to keep the prompt sane.
        slim = [
            {**h, "base": (h["base"] or "")[:400], "head": (h["head"] or "")[:400]}
            for h in interesting[:30]
        ]
        resp = await client.messages.create(
            model="default",
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": _COMMENTARY_PROMPT.format(
                        hunks_json=json.dumps(slim, ensure_ascii=False)
                    ),
                }
            ],
        )
        raw = "\n".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
        parsed = _extract_json(raw) or {}
        for c in parsed.get("hunks", []):
            try:
                commentary[int(c.get("index"))] = c
            except (TypeError, ValueError):
                pass

    annotated_hunks: list[dict] = []
    for h in interesting:
        c = commentary.get(h["index"], {})
        annotated_hunks.append(
            {
                "index": h["index"],
                "kind": h["kind"],
                "base": h["base"],
                "head": h["head"],
                "commentary": c.get("commentary", ""),
                "severity": c.get("severity", "low"),
            }
        )

    # Locate hunk lines in the head text for the diff annotation overlay.
    annotations: list[dict] = []
    line = 0
    for h in hunks_raw:
        head_lines = h.head.count("\n")
        if h.kind != "equal":
            note = commentary.get(_index_in(hunks_raw, h), {}).get("commentary", "")
            if note:
                annotations.append({"line": line + 1, "message": note})
        line += head_lines

    arts: list[dict] = [
        A.diff(
            f"Perbandingan vs {base_label or 'baseline'}",
            base_text,
            head_text,
            annotations=annotations,
        )
    ]
    if annotated_hunks:
        arts.append(
            A.table(
                "Ringkasan perubahan",
                ["#", "Jenis", "Severity", "Komentar"],
                [
                    [h["index"], h["kind"], h["severity"], h["commentary"][:200]]
                    for h in annotated_hunks
                ],
            )
        )

    return {
        "status": "ok",
        "base_label": base_label,
        "hunks": annotated_hunks,
        "artifacts": arts,
    }


def _index_in(hunks: list, target) -> int:
    for i, h in enumerate(hunks):
        if h is target:
            return i
    return -1


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
