"""Cross-encoder reranker that distils the top-50 candidate set to top-k.

We use Claude Haiku as the scoring model. Why not a dedicated BGE or
ColBERT reranker?
  - Zero extra infra: no model server, no separate dependency.
  - Empirically very accurate at relevance judgements.
  - Latency is one Haiku call per ~10 candidates, with all candidates
    in a single batched prompt — well under 1 second.
  - We already pay for prompt caching on the query side.

Falls back to identity (no reranking) when there's no API key. That
keeps tests and dev environments working without network.
"""
from __future__ import annotations

import json
import logging
import re

from backend.config import get_settings

_settings = get_settings()
_log = logging.getLogger(__name__)


_SYSTEM = """\
You are a relevance grader for an Indonesian legal search system. Given a
user query and N candidate passages, return a JSON array of N integers
in the range 0..10, where each integer is your assessed relevance of
that candidate to the query. Output ONLY the JSON array — no preamble,
no markdown fences, no explanation.
"""


def _candidate_text(c: dict) -> str:
    # Each candidate dict can carry different keys depending on its
    # source (pasal vs DocumentChunk). Use whatever's there.
    for k in ("teks", "text", "contextual_text", "content"):
        v = c.get(k)
        if v:
            return v[:1200]
    return json.dumps(c, ensure_ascii=False)[:1200]


def _parse_scores(raw: str, n: int) -> list[int]:
    # Salvage a JSON array from the model output even if it stuck
    # something else in.
    m = re.search(r"\[[\d,\s]+\]", raw)
    if not m:
        return [5] * n
    try:
        arr = json.loads(m.group(0))
        if not isinstance(arr, list):
            return [5] * n
        out = [int(x) if isinstance(x, (int, float)) else 5 for x in arr]
        if len(out) < n:
            out = out + [5] * (n - len(out))
        return out[:n]
    except Exception:  # noqa: BLE001
        return [5] * n


async def rerank(
    query: str,
    candidates: list[dict],
    *,
    top_k: int = 10,
) -> list[dict]:
    """Score `candidates` against `query`, return top_k by descending score.

    Each candidate gets a `_rerank_score` field added in place. Non-LLM
    fallback returns the first top_k candidates unchanged (assumes the
    upstream retriever already sorted by hybrid score).
    """
    if not candidates:
        return []
    if not _settings.anthropic_api_key or len(candidates) <= top_k:
        return candidates[:top_k]

    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=_settings.anthropic_api_key)

    numbered = "\n".join(
        f"<candidate index={i}>\n{_candidate_text(c)}\n</candidate>" for i, c in enumerate(candidates)
    )
    user_msg = (
        f"<query>{query}</query>\n\n{numbered}\n\n"
        f"Return ONLY a JSON array of {len(candidates)} integers (0..10), "
        f"one score per candidate index in order."
    )

    try:
        resp = await client.messages.create(
            model=_settings.anthropic_model_fast,
            max_tokens=512,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    except Exception as e:  # noqa: BLE001
        _log.warning("rerank: scoring call failed: %s", e)
        return candidates[:top_k]

    scores = _parse_scores(raw, len(candidates))
    for c, s in zip(candidates, scores):
        c["_rerank_score"] = s
    candidates.sort(key=lambda c: c.get("_rerank_score", 0), reverse=True)
    return candidates[:top_k]
