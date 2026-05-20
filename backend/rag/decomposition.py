"""Query decomposition — break a complex legal question into sub-queries.

Examples we want to decompose:

  "Apakah Pasal 1320 KUHPerdata masih relevan setelah UU Cipta Kerja
   dan bagaimana dampaknya pada kontrak B2B?"
    → ["Apa isi Pasal 1320 KUHPerdata?",
       "Apa yang diubah UU Cipta Kerja terkait Pasal 1320?",
       "Bagaimana dampak perubahan tersebut pada kontrak B2B?"]

  "Bandingkan ketentuan PHK dalam UU 13/2003 vs UU 11/2020 untuk PKWT"
    → ["Apa ketentuan PHK PKWT dalam UU 13/2003?",
       "Apa ketentuan PHK PKWT dalam UU 11/2020?",
       "Apa perbedaan keduanya?"]

The agent calls this when a single retrieval returns weak or conflicting
evidence, or when the question contains conjunctions ("dan", "vs",
"setelah", "bagaimana dampaknya"). For each sub-query we retrieve
independently, then synthesise an answer over the merged evidence.

Falls back to `[query]` (no decomposition) when no API key is set.
"""
from __future__ import annotations

import json
import logging
import re

_log = logging.getLogger(__name__)


_PROMPT = """\
Pecah pertanyaan hukum berikut menjadi sub-pertanyaan yang independen
dan retrievable (bisa dijawab masing-masing dari korpus peraturan
Indonesia). Maksimum 4 sub-pertanyaan. Pertanyaan yang sudah atomic
tidak perlu dipecah — kembalikan array dengan satu elemen sama dengan
input. Output HANYA JSON array string, tanpa preamble:

["sub-pertanyaan 1", "sub-pertanyaan 2", ...]

Pertanyaan: {q}
"""


_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


async def decompose(query: str, *, max_subqueries: int = 4) -> list[str]:
    """Return a list of sub-queries. Always includes the original at the end."""
    if not query.strip():
        return []
    try:
        from backend.config import get_settings
        settings = get_settings()
    except Exception:  # noqa: BLE001 — keeps callers alive without pydantic in test env
        return [query]
    if not settings.anthropic_api_key:
        return [query]
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    try:
        resp = await client.messages.create(
            model=settings.anthropic_model_fast,
            max_tokens=400,
            messages=[{"role": "user", "content": _PROMPT.format(q=query)}],
        )
        raw = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    except Exception as e:  # noqa: BLE001
        _log.warning("decompose: %s", e)
        return [query]

    m = _ARRAY_RE.search(raw)
    if not m:
        return [query]
    try:
        arr = json.loads(m.group(0))
    except json.JSONDecodeError:
        return [query]
    if not isinstance(arr, list):
        return [query]
    cleaned = [s.strip() for s in arr if isinstance(s, str) and s.strip()]
    if not cleaned:
        return [query]
    return cleaned[:max_subqueries]
