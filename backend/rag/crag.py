"""Corrective RAG (CRAG) — grade retrieved evidence and self-correct.

Three-state grading:
  - SUFFICIENT  → answer directly from evidence
  - PARTIAL     → augment with a refined sub-query, then answer
  - INSUFFICIENT→ rewrite the query (decomposition + HyDE) and retry

The grader is the fast model (Haiku). It returns a verdict + a brief
reason that the caller can surface in the trace.

Without an API key we fall back to a score-threshold heuristic so dev
and tests still work offline.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from enum import StrEnum

_log = logging.getLogger(__name__)


class Verdict(StrEnum):
    SUFFICIENT = "sufficient"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"


@dataclass(slots=True)
class Grade:
    verdict: Verdict
    reason: str
    refined_query: str | None = None


_PROMPT = """\
Anda adalah grader retrieval untuk sistem hukum Indonesia. Diberikan
sebuah pertanyaan dan N passage hasil retrieval, nilai apakah evidence
yang ada cukup untuk menjawab pertanyaan secara akurat. Jika tidak
cukup, sarankan kueri yang diperbaiki.

Kembalikan HANYA JSON:

{{
  "verdict": "sufficient" | "partial" | "insufficient",
  "reason": "kalimat singkat",
  "refined_query": "kueri yang diperbaiki (kalau verdict bukan sufficient, jika tidak null)"
}}

Pertanyaan: {q}

Passage:
{passages}
"""


def _passage_block(hits: list[dict]) -> str:
    parts: list[str] = []
    for i, h in enumerate(hits[:8]):
        for k in ("teks", "text", "contextual_text", "snippet"):
            v = h.get(k)
            if v:
                parts.append(f"[{i}] {str(v)[:600]}")
                break
    return "\n\n".join(parts) or "(no passages)"


async def grade(question: str, hits: list[dict]) -> Grade:
    """LLM-graded if API key available; threshold heuristic otherwise."""
    if not hits:
        return Grade(Verdict.INSUFFICIENT, "no hits", refined_query=question)

    api_key = _api_key()
    if not api_key:
        top = float(hits[0].get("score", 0.0))
        if top < 0.3:
            return Grade(Verdict.INSUFFICIENT, f"low top score {top:.2f}", refined_query=question)
        if top < 0.5:
            return Grade(Verdict.PARTIAL, f"middling top score {top:.2f}")
        return Grade(Verdict.SUFFICIENT, "ok")

    from backend.llm import get_client

    client = get_client()
    try:
        resp = await client.messages.create(
            model="fast",
            max_tokens=400,
            messages=[
                {
                    "role": "user",
                    "content": _PROMPT.format(q=question, passages=_passage_block(hits)),
                }
            ],
        )
        raw = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    except Exception as e:  # noqa: BLE001
        _log.warning("crag.grade: %s", e)
        return Grade(Verdict.PARTIAL, f"grader failed: {e}")

    parsed = _extract_json(raw)
    if not parsed:
        return Grade(Verdict.PARTIAL, "grader returned unparseable output")

    raw_verdict = str(parsed.get("verdict", "partial")).lower()
    try:
        verdict = Verdict(raw_verdict)
    except ValueError:
        verdict = Verdict.PARTIAL
    return Grade(
        verdict=verdict,
        reason=str(parsed.get("reason", "")).strip()[:240] or "(no reason)",
        refined_query=parsed.get("refined_query") or None,
    )


def _api_key() -> str | None:
    """Return the active provider's key, or None when running offline.

    Wrapped in try/except so the heuristic path keeps working in test
    environments that don't ship pydantic.
    """
    try:
        from backend.config import get_settings
        return get_settings().llm_api_key()
    except Exception:  # noqa: BLE001
        return None


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
