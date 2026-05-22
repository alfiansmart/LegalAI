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
    from backend.config import get_settings
    from backend.documents import service
    from backend.llm import get_client

    args = args or {}
    raw_text: str | None = args.get("raw_text")
    document_id = args.get("document_id")
    if not raw_text and document_id:
        raw_text = await service.latest_content(int(document_id))
    if not raw_text:
        return {"status": "error", "message": "need raw_text or document_id"}

    settings = get_settings()
    if not settings.llm_api_key():
        return {"status": "error", "message": "LLM provider API key not configured"}

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

    client = get_client()
    resp = await client.messages.create(
        model="default",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    text_blocks = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
    payload_text = "\n".join(text_blocks).strip()
    parsed = _extract_json(payload_text) or {}
    if not parsed:
        return {"status": "error", "message": "failed to parse model output", "raw": payload_text[:500]}

    findings = parsed.get("findings", [])
    missing = parsed.get("missing_standard_clauses", [])
    return {
        "status": "ok",
        "summary": parsed.get("summary", ""),
        "findings": findings,
        "missing_standard_clauses": missing,
        "artifacts": _build_artifacts(parsed.get("summary", ""), findings, missing),
    }


def _build_artifacts(summary: str, findings: list[dict], missing: list[str]) -> list[dict]:
    from backend.agents import artifacts as A

    out: list[dict] = []

    # 1) Heatmap: clause excerpt x severity. One row per finding, one
    # cell shaded by the finding's severity.
    if findings:
        severities = ["low", "medium", "high", "critical"]
        rows = [f.get("id") or f"F{i + 1}" for i, f in enumerate(findings)]
        cells = []
        for f in findings:
            row = []
            sev = (f.get("severity") or "low").lower()
            for s in severities:
                if s == sev:
                    row.append({"severity": s, "label": s[:1].upper()})
                else:
                    row.append(None)
            cells.append(row)
        out.append(A.heatmap("Severity per finding", rows, severities, cells))

    # 2) Findings table — sortable, exportable.
    if findings:
        cols = ["ID", "Severity", "Kategori", "Klausa", "Rekomendasi", "Pasal"]
        rows_t = []
        for i, f in enumerate(findings):
            rows_t.append(
                [
                    f.get("id") or f"F{i + 1}",
                    f.get("severity", ""),
                    f.get("category", ""),
                    (f.get("clause_excerpt") or "")[:120],
                    (f.get("recommendation") or "")[:160],
                    ", ".join(f.get("pasal_refs") or []),
                ]
            )
        out.append(A.table("Findings", cols, rows_t, caption=summary[:200] or None))

    # 3) Missing-clauses chart (counts by category).
    if missing:
        out.append(
            A.chart(
                "Klausa yang hilang",
                kind="bar",
                series=[{"name": "missing", "data": [{"x": c, "y": 1} for c in missing]}],
            )
        )

    return out


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
