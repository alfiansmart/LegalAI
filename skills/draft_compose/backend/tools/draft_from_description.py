"""Generate a tailored Indonesian perjanjian draft from a natural-language brief.

Output is a markdown-formatted document (rendered live by TipTap) with
proper Pasal/ayat/huruf numbering and a closing block. The skill also
emits a `tree` artifact showing the generated structure so the lawyer
can spot missing clauses before committing.
"""
from __future__ import annotations

import json
import re


_DRAFT_PROMPT = """\
Anda adalah penyusun perjanjian hukum Indonesia. Berdasarkan deskripsi
pengguna berikut, susun draft {doc_kind} lengkap.

Deskripsi pengguna:
\"\"\"{description}\"\"\"

Aturan format:
- Output dalam Bahasa Indonesia formal hukum.
- Struktur wajib: JUDUL, PEMBUKAAN (premis "Pada hari ini..." +
  identitas para pihak), PASAL-PASAL (penomoran Pasal 1, Pasal 2, dst.),
  PENUTUP (tanggal + tanda tangan).
- Pasal yang umum: Definisi, Lingkup, Hak dan Kewajiban, Jangka Waktu,
  Force Majeure, Pengakhiran, Penyelesaian Sengketa.
- Sub-ayat ditulis "(1) ...", "(2) ..."; huruf "a. ...", "b. ...".
- Setiap rujukan peraturan ditulis "Pasal X ayat (Y) <Peraturan>".

Kembalikan HANYA JSON valid dengan skema:

{{
  "title": "<judul singkat untuk dokumen, mis. 'NDA PT Alpha vs PT Beta'>",
  "kind": "{doc_kind}",
  "markdown": "<dokumen lengkap dalam markdown>",
  "outline": [
    {{"label": "PEMBUKAAN", "kind": "section"}},
    {{"label": "Pasal 1 — Definisi", "kind": "pasal"}},
    ...
  ],
  "missing_inputs": ["nilai_kontrak", "alamat_para_pihak", ...]
}}

`missing_inputs` adalah field yang sebaiknya pengguna isi setelah
membaca draft (mis. "alamat lengkap PT Alpha", "nomor rekening
pembayaran"). Boleh kosong jika deskripsi sudah lengkap.
"""


async def execute(agent=None, args: dict | None = None) -> dict:
    from backend.agents import artifacts as A
    from backend.config import get_settings
    from backend.llm import get_client
    from backend.documents import service as doc_service

    args = args or {}
    description = (args.get("description") or "").strip()
    if not description:
        return {"status": "error", "message": "need description"}
    doc_kind = (args.get("doc_kind") or "perjanjian").strip()
    matter_id = args.get("matter_id")
    title_hint = args.get("title")

    settings = get_settings()
    if not settings.llm_api_key():
        return {"status": "error", "message": "LLM provider API key not configured"}

    client = get_client()
    resp = await client.messages.create(
        model="default",
        max_tokens=6000,
        messages=[
            {
                "role": "user",
                "content": _DRAFT_PROMPT.format(
                    doc_kind=doc_kind, description=description
                ),
            }
        ],
    )
    raw = "\n".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
    parsed = _extract_json(raw)
    if not parsed or "markdown" not in parsed:
        return {"status": "error", "message": "failed to parse model output", "raw": raw[:500]}

    title = title_hint or parsed.get("title") or f"Draft {doc_kind}"
    markdown = parsed["markdown"]
    outline = parsed.get("outline") or []
    missing = parsed.get("missing_inputs") or []

    session_id = getattr(agent, "session_id", None)
    document_id = await doc_service.create_draft(
        user_id=session_id,
        title=title,
        kind=_resolve_kind(parsed.get("kind") or doc_kind),
        content=markdown,
        matter_id=matter_id,
    )

    artifacts: list[dict] = []
    if outline:
        artifacts.append(
            A.tree(
                "Struktur draft",
                {
                    "label": title,
                    "children": [
                        {"label": str(n.get("label", "?"))} for n in outline
                    ],
                },
            )
        )
    if missing:
        artifacts.append(
            A.table(
                "Field yang perlu dilengkapi",
                ["#", "Field"],
                [[i + 1, m] for i, m in enumerate(missing)],
                caption="Lengkapi field-field ini di editor sebelum dokumen ditandatangani.",
            )
        )

    return {
        "status": "ok",
        "document_id": document_id,
        "title": title,
        "content_preview": markdown[:600],
        "outline": outline,
        "missing_inputs": missing,
        "artifacts": artifacts,
    }


_VALID_KINDS = {
    "perjanjian",
    "memo",
    "opini",
    "somasi",
    "gugatan",
    "surat_kuasa",
    "kontrak_upload",
    "lainnya",
}


def _resolve_kind(raw: str) -> str:
    raw = (raw or "").strip().lower()
    return raw if raw in _VALID_KINDS else "perjanjian"


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
