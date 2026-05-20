"""Anthropic-style contextual retrieval.

For each chunk, before we embed it we ask a fast model to write a 1-2
sentence blurb that situates the chunk inside the document as a whole.
This blurb is prepended to the chunk text, and *that* augmented string
is what we embed and index.

Empirically (per Anthropic's published results) this lifts retrieval
recall ~35% on long documents. The reason: a clause that says "Within
30 days" is uninformative on its own; the same clause prefixed with
"This is the cure period in the Termination section of Vendor IT
Contract …" is searchable for "berapa lama waktu sembuh wanprestasi".

The bill is one Haiku call per chunk at ingest time. Because the full
document is the same for every chunk in a single ingest, we mark it
with `cache_control: ephemeral` — the document prefix is paid for once
and reused for every subsequent chunk in the same ingest.

Pure-text fallback: if no ANTHROPIC_API_KEY is configured we return a
deterministic structural blurb based on the breadcrumb. The pipeline
still works, just without the LLM-quality augmentation.
"""
from __future__ import annotations

import asyncio
import logging

from backend.config import get_settings

_settings = get_settings()
_log = logging.getLogger(__name__)


_PROMPT = """\
You will be given a long legal document and one short chunk from inside it.
Write a single sentence (≤ 40 words, in Bahasa Indonesia if the document is
Bahasa, otherwise in English) that situates the chunk inside the document:
which section / pasal / clause it belongs to and what topic it covers.
Do not summarise the chunk's content beyond that — produce only the
contextual locator sentence, nothing else. No preamble, no quotes.
"""


def _fallback_blurb(breadcrumb: str, parent_summary: str) -> str:
    parts = [p for p in (breadcrumb, parent_summary) if p]
    if not parts:
        return ""
    return f"Konteks: {parts[0]}."


async def contextualise_chunks(
    full_text: str,
    chunks_text: list[str],
    *,
    breadcrumbs: list[str] | None = None,
    parent_summaries: list[str] | None = None,
    concurrency: int = 4,
) -> list[str]:
    """Generate a context blurb for every chunk.

    Returns a list of blurbs the same length as `chunks_text`. Each
    blurb should be prepended (with a separator) to the corresponding
    chunk text before embedding.
    """
    n = len(chunks_text)
    breadcrumbs = breadcrumbs or [""] * n
    parent_summaries = parent_summaries or [""] * n

    if not _settings.anthropic_api_key:
        return [_fallback_blurb(b, p) for b, p in zip(breadcrumbs, parent_summaries)]

    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=_settings.anthropic_api_key)
    sem = asyncio.Semaphore(concurrency)
    blurbs: list[str] = [""] * n

    # Truncate document if absurdly long — keep the model's input budget sane.
    doc = full_text
    if len(doc) > 400_000:
        doc = doc[:400_000]

    async def _one(i: int, chunk_text: str) -> None:
        async with sem:
            try:
                resp = await client.messages.create(
                    model=_settings.anthropic_model_fast,
                    max_tokens=120,
                    system=_PROMPT,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "<document>\n" + doc + "\n</document>",
                                    "cache_control": {"type": "ephemeral"},
                                },
                                {
                                    "type": "text",
                                    "text": (
                                        f"<location>{breadcrumbs[i]}</location>\n"
                                        f"<chunk>\n{chunk_text}\n</chunk>"
                                    ),
                                },
                            ],
                        }
                    ],
                )
                parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
                blurbs[i] = (parts[0].strip() if parts else "")
            except Exception as e:  # noqa: BLE001
                _log.warning("contextualise_chunks: chunk %d failed: %s", i, e)
                blurbs[i] = _fallback_blurb(breadcrumbs[i], parent_summaries[i])

    await asyncio.gather(*(_one(i, c) for i, c in enumerate(chunks_text)))
    # Anything that came back empty: fall back deterministically.
    for i, b in enumerate(blurbs):
        if not b:
            blurbs[i] = _fallback_blurb(breadcrumbs[i], parent_summaries[i])
    return blurbs


def augment_for_embedding(chunk_text: str, blurb: str) -> str:
    """Combine context blurb + raw chunk into the string we'll embed."""
    if not blurb:
        return chunk_text
    return f"{blurb}\n\n{chunk_text}"
