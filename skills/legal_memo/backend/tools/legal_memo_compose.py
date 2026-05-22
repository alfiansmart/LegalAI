"""Compose a structured Indonesian legal memo (Isu / Fakta / Analisis /
Kesimpulan) backed by retrieved pasal evidence."""
from __future__ import annotations

import json
import re


_MEMO_PROMPT = """\
Anda adalah penyusun memo hukum untuk yurisdiksi Republik Indonesia.

Berdasarkan isu, fakta, dan bukti (pasal) berikut, hasilkan HANYA JSON
valid dengan skema:

{{
  "analysis": "paragraf analisis hukum, kutip pasal yang relevan dalam format 'Pasal X ayat (Y) <Peraturan>'",
  "conclusion": "kesimpulan dan rekomendasi tindak lanjut (1-2 paragraf)"
}}

Isu: {issue}

Fakta: {facts}

Bukti yang tersedia:
{evidence_block}
"""


async def execute(agent=None, args: dict | None = None) -> dict:
    from backend.config import get_settings
    from backend.documents import service, templates
    from backend.llm import get_client

    args = args or {}
    issue = args.get("issue") or ""
    facts = args.get("facts") or ""
    evidence = args.get("evidence") or []

    settings = get_settings()
    if not settings.llm_api_key():
        return {"status": "error", "message": "LLM provider API key not configured"}

    evidence_block = (
        "\n".join(
            f"- {e.get('peraturan', '?')} Pasal {e.get('pasal', '?')}"
            f"{(' ayat (' + e['ayat'] + ')') if e.get('ayat') else ''}: "
            f"{(e.get('snippet') or e.get('teks') or '')[:300]}"
            for e in evidence
        )
        or "(tidak ada bukti tersaji — minta tool peraturan_search jika perlu)"
    )

    prompt = _MEMO_PROMPT.format(
        issue=issue, facts=facts, evidence_block=evidence_block
    )

    client = get_client()
    resp = await client.messages.create(
        model="default",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    text_blocks = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
    parsed = _extract_json("\n".join(text_blocks)) or {}
    analysis = parsed.get("analysis") or "(analisis tidak dihasilkan)"
    conclusion = parsed.get("conclusion") or "(kesimpulan tidak dihasilkan)"

    # Render via template + persist
    content = templates.render(
        "legal_memo",
        {
            "issue": issue,
            "facts": facts,
            "analysis": analysis,
            "conclusion": conclusion,
            "evidence": evidence,
        },
    )
    session_id = getattr(agent, "session_id", None)
    doc_id = await service.create_draft(
        user_id=session_id,
        title=f"Memo: {issue[:60]}",
        kind="memo",
        content=content,
        template_id="legal_memo",
    )
    return {
        "status": "ok",
        "document_id": doc_id,
        "analysis": analysis,
        "conclusion": conclusion,
        "memo": content,
        "content_preview": content[:600],
        "artifacts": _memo_artifacts(issue, evidence),
    }


def _memo_artifacts(issue: str, evidence: list) -> list[dict]:
    from backend.agents import artifacts as A

    out: list[dict] = []
    # Evidence table — what pasal grounds the memo.
    if evidence:
        rows = []
        for e in evidence:
            label = f"{e.get('peraturan', '?')} Pasal {e.get('pasal', '?')}"
            if e.get("ayat"):
                label += f" ayat ({e['ayat']})"
            rows.append([label, (e.get("snippet") or e.get("teks") or "")[:300]])
        out.append(A.table("Bukti Pasal", ["Rujukan", "Kutipan"], rows))
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
