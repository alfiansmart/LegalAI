"""Extract structured facts from a legal document.

Emits one table artifact per category (parties / dates / money /
obligations / jurisdiction / governing_law) so the frontend renders
them as separate, scrollable tables.
"""
from __future__ import annotations

import json
import re

from sqlalchemy import select

from backend.agents import artifacts as A
from backend.config import get_settings
from backend.db import models
from backend.db.session import session_scope


_EXTRACT_PROMPT = """\
Ekstrak fakta dari dokumen hukum berikut. Kembalikan HANYA JSON valid:

{{
  "parties": [{{"name": "...", "role": "Pihak Pertama|Penjual|Klien|..."}}],
  "dates": [{{"label": "Tanggal Efektif", "value": "2025-01-01"}}],
  "money": [{{"label": "Nilai Kontrak", "amount": "1.500.000.000", "currency": "IDR"}}],
  "obligations": [{{"party": "...", "obligation": "...", "deadline": "..."}}],
  "jurisdiction": {{"governing_law": "Hukum Republik Indonesia",
                    "forum": "Pengadilan Negeri Jakarta Pusat / BANI"}},
  "law_references": ["KUHPerdata Pasal 1320", "UU 11/2008"]
}}

Dokumen:
<<<
{text}
>>>"""


async def execute(agent=None, args: dict | None = None) -> dict:
    from backend.llm import get_client

    args = args or {}
    document_id = args.get("document_id")
    if not document_id:
        return {"status": "error", "message": "need document_id"}
    document_id = int(document_id)

    async with session_scope() as s:
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
    if not text:
        return {"status": "error", "message": "document has no content"}

    settings = get_settings()
    if not settings.llm_api_key():
        return {"status": "error", "message": "LLM provider API key not configured"}

    client = get_client()
    resp = await client.messages.create(
        model="default",
        max_tokens=4096,
        messages=[{"role": "user", "content": _EXTRACT_PROMPT.format(text=text[:80_000])}],
    )
    raw = "\n".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
    parsed = _extract_json(raw) or {}
    if not parsed:
        return {"status": "error", "message": "failed to parse model output", "raw": raw[:500]}

    parties = parsed.get("parties", []) or []
    dates = parsed.get("dates", []) or []
    money = parsed.get("money", []) or []
    obligations = parsed.get("obligations", []) or []
    jur = parsed.get("jurisdiction", {}) or {}
    law_refs = parsed.get("law_references", []) or []

    arts: list[dict] = []
    if parties:
        arts.append(
            A.table(
                "Para Pihak",
                ["Nama", "Peran"],
                [[p.get("name", ""), p.get("role", "")] for p in parties],
            )
        )
    if dates:
        arts.append(
            A.table(
                "Tanggal Penting",
                ["Label", "Tanggal"],
                [[d.get("label", ""), d.get("value", "")] for d in dates],
            )
        )
    if money:
        arts.append(
            A.table(
                "Jumlah Uang",
                ["Label", "Nominal", "Mata uang"],
                [[m.get("label", ""), m.get("amount", ""), m.get("currency", "")] for m in money],
            )
        )
    if obligations:
        arts.append(
            A.table(
                "Kewajiban",
                ["Pihak", "Kewajiban", "Tenggat"],
                [[o.get("party", ""), o.get("obligation", ""), o.get("deadline", "")] for o in obligations],
            )
        )
    if jur:
        arts.append(
            A.table(
                "Jurisdiksi",
                ["Field", "Value"],
                [
                    ["Governing Law", jur.get("governing_law", "")],
                    ["Forum", jur.get("forum", "")],
                ],
            )
        )
    if law_refs:
        arts.append(
            A.table(
                "Rujukan Hukum",
                ["Peraturan"],
                [[r] for r in law_refs],
            )
        )

    # Persist entities for downstream queries.
    await _persist_entities(document_id, parties, dates, money, obligations, law_refs)

    return {
        "status": "ok",
        "parties": parties,
        "dates": dates,
        "money": money,
        "obligations": obligations,
        "jurisdiction": jur,
        "law_references": law_refs,
        "artifacts": arts,
    }


async def _persist_entities(
    document_id: int,
    parties: list,
    dates: list,
    money: list,
    obligations: list,
    law_refs: list,
) -> None:
    async with session_scope() as s:
        for p in parties:
            s.add(
                models.DocumentEntity(
                    document_id=document_id, kind="party", value=p.get("name", ""), payload=p
                )
            )
        for d in dates:
            s.add(
                models.DocumentEntity(
                    document_id=document_id, kind="date", value=d.get("value", ""), payload=d
                )
            )
        for m in money:
            s.add(
                models.DocumentEntity(
                    document_id=document_id, kind="money", value=m.get("amount", ""), payload=m
                )
            )
        for o in obligations:
            s.add(
                models.DocumentEntity(
                    document_id=document_id,
                    kind="obligation",
                    value=o.get("obligation", ""),
                    payload=o,
                )
            )
        for r in law_refs:
            s.add(
                models.DocumentEntity(
                    document_id=document_id, kind="law", value=r, payload={"raw": r}
                )
            )


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
