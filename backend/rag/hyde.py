"""Hypothetical Document Embeddings (HyDE).

A user query like "berapa lama jangka waktu perpanjangan PKWT" doesn't
look much like the answer they're after ("PKWT dapat diperpanjang
paling lama lima tahun setelah perubahan UU Cipta Kerja"). Embedding
the *query* and matching it to *passage embeddings* loses recall —
especially for vague or jargon-light questions.

HyDE: ask a fast LLM to write a *hypothetical answer* to the query
(it can hallucinate; we don't display it). Embed the hypothetical
answer and use that vector to retrieve real passages. The retrieved
passages are then fed to the slow LLM for the real answer.

We expose two functions:
  - `hypothetical_answer(q)` — generates the hypothetical text
  - `hyde_embedding(q)` — convenience: hypothetical_answer → embed

Falls back to embedding the raw query when no API key is set.
"""
from __future__ import annotations

import logging

_log = logging.getLogger(__name__)


_PROMPT = """\
Tulis satu paragraf jawaban hipotetis (3-5 kalimat) untuk pertanyaan
hukum berikut. Jawaban boleh salah secara faktual — tujuannya hanya
membantu retrieval semantik atas korpus peraturan Indonesia. Gunakan
istilah hukum yang biasa muncul di pasal-pasal terkait. Tanpa
disclaimer, tanpa preamble, tanpa kutipan.

Pertanyaan: {q}
"""


async def hypothetical_answer(query: str) -> str:
    if not query.strip():
        return ""
    try:
        from backend.config import get_settings
        settings = get_settings()
    except Exception:  # noqa: BLE001
        return query
    if not settings.llm_api_key():
        return query
    from backend.llm import get_client

    client = get_client()
    try:
        resp = await client.messages.create(
            model="fast",
            max_tokens=350,
            messages=[{"role": "user", "content": _PROMPT.format(q=query)}],
        )
        parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
        out = "\n".join(parts).strip()
        return out or query
    except Exception as e:  # noqa: BLE001
        _log.warning("hyde.hypothetical_answer: %s", e)
        return query


async def hyde_embedding(query: str) -> list[float]:
    """Generate a hypothetical answer and embed it. The embedding is
    what the retriever should query with — not the raw user question."""
    from backend.rag.embeddings import embed_one

    hypo = await hypothetical_answer(query)
    return embed_one(hypo, is_query=False)
