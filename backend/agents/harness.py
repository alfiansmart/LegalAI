"""Claude-Code-style agent harness.

Responsibilities:
  - Streaming tool-use loop with bounded turns.
  - Subagent dispatch for heavy work (research / review).
  - Context budget manager (auto-compaction into episodic memory).
  - Prompt-cache the persona + skill prompts + retrieved pasal block.
  - Plan-then-act for complex queries.
  - Citation faithfulness verifier pass for any drafted document.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from backend.agents import personas
from backend.config import get_settings

_settings = get_settings()


@dataclass(slots=True)
class HarnessResult:
    session_id: str
    reply: str
    citations: list[dict] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)


class AgentHarness:
    def __init__(self, agent_name: str = "asisten_hukum", session_id: str | None = None):
        self.persona = personas.get(agent_name)
        self.session_id = session_id or uuid.uuid4().hex
        self.trace: list[dict] = []
        self.citations: list[dict] = []

    async def run(self, user_message: str, as_of: str | None = None) -> HarnessResult:
        """Phase-0 stub: returns a placeholder. The real loop lands in Phase 1.

        Planned shape:
          1. Load episodic + semantic memory tools.
          2. (Plan-then-act) Ask fast model for a plan if message is complex.
          3. Tool loop with Anthropic streaming + tool_use blocks:
               - peraturan_search / pasal_lookup / citation_trace / …
               - cache_control on persona + skill prompts + corpus prefix
          4. CRAG: grade evidence; rewrite query on insufficient.
          5. Verifier subagent re-reads any drafted artifact for citation
             faithfulness before returning.
          6. Persist Turn rows; extract memory candidates post-turn.
        """
        reply = (
            f"[Phase-0 stub] Agent '{self.persona.name}' menerima pesan: {user_message!r}. "
            "Loop tool-use Anthropic + RAG + verifier akan diaktifkan pada Phase 1."
        )
        return HarnessResult(
            session_id=self.session_id, reply=reply, citations=self.citations, trace=self.trace
        )

    # ---- Helpers (implemented in Phase 1) ----

    async def _plan(self, message: str) -> list[str]:
        """Decompose complex queries into sub-questions using the fast model."""
        raise NotImplementedError

    async def _subagent(self, task: str, skills: list[str]) -> dict[str, Any]:
        """Dispatch a heavy task to a fresh subagent; returns compact summary."""
        raise NotImplementedError

    async def _compact_if_needed(self, messages: list[dict]) -> list[dict]:
        """Token-budget check; if exceeded, summarize older turns into episodic memory."""
        raise NotImplementedError

    async def _verify_citations(self, draft_text: str) -> tuple[str, list[dict]]:
        """For every Pasal cited, fetch text & ask: 'does it support the claim?'.
        Drop / rewrite unsupported claims."""
        raise NotImplementedError
