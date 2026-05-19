"""Review an Indonesian contract: flag risky clauses with severity +
pasal anchors. Anthropic-powered, structured output."""
from __future__ import annotations

import json
import re


_REVIEW_PROMPT = """\
Anda adalah reviewer hukum kontrak untuk yurisdiksi Republik Indonesia.

Lakukan review terhadap kontrak berikut dan kembalikan HANYA JSON valid
(tanpa penjelasan di luar JSON) dengan skema:

{{
  "summary": "ringkasan eksekutif maksimum 3 kalimat",
  "findings": [
    {{
      "id": "F1",
      "clause_excerpt": "kutipan singkat klausa (<=200 char)",
      "issue": "deskripsi masalah",
      "severity": "low|medium|high|critical",
      "category": "missing|risky|ambiguous|unfair|noncompliant",
      "recommendation": "saran perbaikan konkret",
      "pasal_refs": ["Pasal 1320 KUHPerdata", "Pasal X UU 27/2022"]
    }}
  ],
  "missing_standard_clauses": ["force_majeure", "arbitrase_bani", ...]
}}

{compliance_block}

Kontrak:
<<<
{contract_text}
>>>"""


async def execute(agent=None, args: dict | None = None) -> dict:
    from anthropic import AsyncAnthropic
    from backend.config import get_settings
    from backend.documents import service

    args = args or {}
    raw_text: str | None = args.get("raw_text")
    document_id = args.get("document_id")
    if not raw_text and document_id:
        raw_text = await service.latest_content(int(document_id))
    if not raw_text:
        return {"status": "error", "message": "need raw_text or document_id"}

    settings = get_settings()
    if not settings.anthropic_api_key:
        return {"status": "error", "message": "ANTHROPIC_API_KEY not set"}

    compliance = args.get("compliance_against") or []
    compliance_block = (
        f"Lakukan compliance check terhadap peraturan berikut: {', '.join(compliance)}.\n"
        if compliance
        else ""
    )

    prompt = _REVIEW_PROMPT.format(
        contract_text=raw_text[:30_000],
        compliance_block=compliance_block,
    )

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    resp = await client.messages.create(
        model=settings.anthropic_model_default,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    text_blocks = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
    payload_text = "\n".join(text_blocks).strip()
    parsed = _extract_json(payload_text) or {}
    if not parsed:
        return {"status": "error", "message": "failed to parse model output", "raw": payload_text[:500]}

    return {
        "status": "ok",
        "summary": parsed.get("summary", ""),
        "findings": parsed.get("findings", []),
        "missing_standard_clauses": parsed.get("missing_standard_clauses", []),
    }


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).rstrip("`").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = _JSON_BLOCK_RE.search(text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
