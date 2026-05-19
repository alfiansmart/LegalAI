"""Corrective RAG: grade retrieved evidence; on insufficient, rewrite & retry."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Verdict(StrEnum):
    SUFFICIENT = "sufficient"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"


@dataclass(slots=True)
class Grade:
    verdict: Verdict
    reason: str


async def grade(question: str, hits: list[dict]) -> Grade:
    """Use the fast LLM to grade evidence quality. Stubbed for Phase 0."""
    if not hits:
        return Grade(Verdict.INSUFFICIENT, "no hits")
    top = hits[0].get("score", 0.0)
    if top < 0.3:
        return Grade(Verdict.INSUFFICIENT, f"low top score {top:.2f}")
    if top < 0.5:
        return Grade(Verdict.PARTIAL, f"middling top score {top:.2f}")
    return Grade(Verdict.SUFFICIENT, "ok")
