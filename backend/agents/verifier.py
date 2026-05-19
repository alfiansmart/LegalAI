"""Citation faithfulness verifier.

Given a drafted answer/document, for each Pasal citation:
  1. Resolve to the actual pasal text via pasal_lookup.
  2. Ask the fast LLM: "does the cited text actually support the claim?"
  3. Drop or flag unsupported claims; rewrite as needed.

This guards against hallucinated pasal numbers — a non-negotiable
requirement for the legal domain.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class VerificationResult:
    cleaned_text: str
    dropped: list[str]
    flagged: list[str]


async def verify(draft_text: str) -> VerificationResult:
    # Phase-0 stub
    return VerificationResult(cleaned_text=draft_text, dropped=[], flagged=[])
