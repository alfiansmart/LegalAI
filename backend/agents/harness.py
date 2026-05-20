"""Claude-Code-style agent harness.

Responsibilities:
  - Anthropic streaming tool-use loop with bounded turns.
  - Prompt-cache the persona + skill prompts on every turn.
  - Resolve every Pasal citation in the final answer to a real pasal_id
    via `pasal_lookup` — citations that don't resolve are dropped (this
    is the citation-faithfulness guard for the legal domain).
  - Persist Turn rows for episodic memory.
  - Apply the safety-disclaimer wrapper.

Subagents, context-budget compaction, plan-then-act, and the verifier
subagent are Phase-2.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from backend.agents import personas
from backend.agents.artifacts import ArtifactCollector
from backend.config import get_settings
from backend.db import models
from backend.db.session import session_scope
from backend.rag.citation import CitationRef, format_citation, parse_citations
from backend.safety.checks import ensure_disclaimer
from backend.skills_loader import SkillRegistry

_settings = get_settings()


@dataclass(slots=True)
class HarnessResult:
    session_id: str
    reply: str
    citations: list[dict] = field(default_factory=list)
    artifacts: list[dict] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)


class AgentHarness:
    def __init__(
        self,
        agent_name: str = "asisten_hukum",
        session_id: str | None = None,
        matter_id: int | None = None,
        registry: SkillRegistry | None = None,
    ):
        self.persona = personas.get(agent_name)
        self.session_id = session_id or uuid.uuid4().hex
        self.matter_id = matter_id
        self.matter_notes: str | None = None
        self.matter_name: str | None = None
        self.registry = registry or SkillRegistry.from_dir(_settings.skills_dir)
        self.trace: list[dict] = []
        self.artifacts = ArtifactCollector()

    # ------------------------------------------------------------------
    # Public entrypoint
    # ------------------------------------------------------------------

    async def run(
        self,
        user_message: str,
        as_of: str | None = None,
        plan_mode: bool = False,
    ) -> HarnessResult:
        if not _settings.anthropic_api_key:
            return HarnessResult(
                session_id=self.session_id,
                reply=(
                    "ANTHROPIC_API_KEY belum dikonfigurasi. Set di `.env` "
                    "untuk mengaktifkan agent."
                ),
            )

        # Lazy import — keeps test runs lean.
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=_settings.anthropic_api_key)

        await self._load_matter()
        system_blocks = self._build_system()
        tools = self.registry.tools_for(self.persona.skills)
        messages = await self._build_initial_messages(user_message, as_of=as_of)

        await self._ensure_session()
        await self._persist_turn("user", user_message)

        # ── Plan mode: emit a plan first (no tools), return it for review.
        if plan_mode:
            plan_text = await self._emit_plan(
                client, user_message, system_blocks, tools_list=tools
            )
            await self._persist_turn("assistant", plan_text)
            return HarnessResult(
                session_id=self.session_id,
                reply=plan_text,
                citations=[],
                trace=[{"event": "plan", "summary": plan_text[:240]}],
            )

        final_text = ""
        for turn in range(_settings.max_agent_turns):
            kwargs: dict[str, Any] = {
                "model": _settings.anthropic_model_default,
                "max_tokens": 4096,
                "system": system_blocks,
                "messages": messages,
            }
            if tools:
                kwargs["tools"] = tools

            resp = await client.messages.create(**kwargs)
            self.trace.append({"event": "turn", "turn": turn, "stop_reason": resp.stop_reason})

            assistant_content: list[dict] = []
            tool_uses = []
            for block in resp.content:
                if block.type == "text":
                    final_text += block.text
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    tool_uses.append(block)
                    assistant_content.append(
                        {
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        }
                    )
            messages.append({"role": "assistant", "content": assistant_content})

            if resp.stop_reason != "tool_use" or not tool_uses:
                break

            tool_results = []
            for tu in tool_uses:
                result = await self._execute_tool(tu.name, dict(tu.input))
                # Skills can emit artifacts by returning {"artifacts": [...]}.
                # We strip them out of what we feed back to the model (the
                # model doesn't need to re-see the artifact payload, just
                # know that the artifact was rendered for the user).
                if isinstance(result, dict) and result.get("artifacts"):
                    self.artifacts.extend(result["artifacts"])
                    result = {
                        **{k: v for k, v in result.items() if k != "artifacts"},
                        "artifacts_emitted": len(result["artifacts"]),
                    }
                self.trace.append(
                    {
                        "event": "tool",
                        "name": tu.name,
                        "args": dict(tu.input),
                        "result_summary": _summarize(result),
                        "status": result.get("status", "ok") if isinstance(result, dict) else "ok",
                    }
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": json.dumps(result, ensure_ascii=False)[:8000],
                    }
                )
            messages.append({"role": "user", "content": tool_results})

        citations = await self._resolve_citations(final_text)
        await self._persist_turn("assistant", final_text, citations=citations)

        return HarnessResult(
            session_id=self.session_id,
            reply=ensure_disclaimer(final_text.strip()),
            citations=citations,
            artifacts=self.artifacts.to_list(),
            trace=self.trace,
        )

    # ------------------------------------------------------------------
    # Plan mode
    # ------------------------------------------------------------------

    async def _emit_plan(
        self,
        client,
        user_message: str,
        system_blocks: list[dict],
        tools_list: list[dict],
    ) -> str:
        tool_names = ", ".join(t["name"] for t in tools_list) or "(tidak ada tool)"
        plan_instructions = (
            "MODE: plan. Jangan eksekusi tool apa pun. Tulis rencana langkah "
            "demi langkah untuk menjawab permintaan pengguna. Format:\n"
            "1. <langkah singkat> — *tool*: <nama_tool> atau (jawab langsung)\n"
            "...\n"
            f"Tool yang tersedia: {tool_names}.\n"
            f"Permintaan: {user_message}"
        )
        resp = await client.messages.create(
            model=_settings.anthropic_model_fast,
            max_tokens=1024,
            system=system_blocks,
            messages=[{"role": "user", "content": plan_instructions}],
        )
        parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
        return "**Rencana:**\n\n" + ("\n".join(parts).strip() or "_(rencana kosong)_")

    # ------------------------------------------------------------------
    # System prompt assembly (with prompt-caching)
    # ------------------------------------------------------------------

    def _build_system(self) -> list[dict]:
        # Block 1: persona prompt (small, stable across sessions).
        # Block 2: concatenated skill prompts (larger, stable across turns).
        # Both blocks marked cache_control=ephemeral so subsequent turns
        # in the same session hit the prompt cache.
        skill_parts: list[str] = []
        for sid in self.persona.skills:
            try:
                sk = self.registry.get(sid)
            except KeyError:
                continue
            if sk.system_prompt:
                skill_parts.append(f"## Skill: {sk.name}\n{sk.system_prompt}")

        blocks: list[dict] = [
            {
                "type": "text",
                "text": self.persona.system_prompt.strip(),
                "cache_control": {"type": "ephemeral"},
            }
        ]
        if skill_parts:
            blocks.append(
                {
                    "type": "text",
                    "text": "\n\n".join(skill_parts).strip(),
                    "cache_control": {"type": "ephemeral"},
                }
            )
        # Matter context — *not* cached, since it changes between matters
        # and is updated by the user during a case.
        if self.matter_notes:
            blocks.append(
                {
                    "type": "text",
                    "text": (
                        f"# Matter aktif: {self.matter_name or '(tanpa nama)'}\n\n"
                        f"Catatan matter (MATTER.md) — gunakan sebagai konteks "
                        f"dan ingat fakta-fakta klien:\n\n{self.matter_notes}"
                    ),
                }
            )
        return blocks

    async def _load_matter(self) -> None:
        if self.matter_id is None:
            return
        async with session_scope() as s:
            m = await s.get(models.Matter, self.matter_id)
            if m:
                self.matter_notes = m.notes_md
                self.matter_name = m.name

    # ------------------------------------------------------------------
    # Tool dispatch
    # ------------------------------------------------------------------

    async def _execute_tool(self, name: str, args: dict) -> dict:
        skill = self.registry.find_by_tool(name)
        if not skill:
            return {"status": "error", "message": f"unknown tool {name!r}"}
        try:
            return await skill.call(name, args, agent=self)
        except Exception as e:  # noqa: BLE001
            return {"status": "error", "message": f"{type(e).__name__}: {e}"}

    # ------------------------------------------------------------------
    # Citation faithfulness
    # ------------------------------------------------------------------

    async def _resolve_citations(self, text: str) -> list[dict]:
        from backend.rag.temporal import pasal_as_of

        out: list[dict] = []
        seen: set[tuple] = set()
        for ref in parse_citations(text):
            if not ref.jenis or not ref.pasal:
                continue
            key = (ref.jenis, ref.nomor, ref.tahun, ref.pasal, ref.ayat, ref.huruf)
            if key in seen:
                continue
            seen.add(key)

            resolved = await pasal_as_of(
                peraturan_jenis=ref.jenis,
                peraturan_nomor=ref.nomor,
                peraturan_tahun=ref.tahun,
                pasal_nomor=ref.pasal,
                ayat_nomor=ref.ayat,
                huruf=ref.huruf,
            )
            out.append(
                {
                    "label": format_citation(ref),
                    "peraturan": (resolved or {}).get("peraturan", {}).get("label", ref.jenis),
                    "pasal": ref.pasal,
                    "ayat": ref.ayat,
                    "huruf": ref.huruf,
                    "pasal_id": (resolved or {}).get("id"),
                    "verified": bool(resolved),
                }
            )
        return out

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def _ensure_session(self) -> None:
        async with session_scope() as s:
            existing = await s.get(models.Session, self.session_id)
            if not existing:
                s.add(
                    models.Session(
                        id=self.session_id,
                        agent=self.persona.id,
                        matter_id=self.matter_id,
                    )
                )
            elif self.matter_id and existing.matter_id != self.matter_id:
                existing.matter_id = self.matter_id

    async def _persist_turn(
        self, role: str, content: str, citations: list[dict] | None = None
    ) -> None:
        async with session_scope() as s:
            s.add(
                models.Turn(
                    session_id=self.session_id,
                    role=role,
                    content=content,
                    citations=citations,
                )
            )

    async def _build_initial_messages(
        self, user_message: str, as_of: str | None
    ) -> list[dict]:
        # Hydrate prior turns as plain user/assistant text (tool_use blocks
        # from prior turns are intentionally dropped — Anthropic accepts
        # plain content arrays and we don't need the prior tool trace).
        from backend.memory.episodic import recent

        prior = await recent(self.session_id, limit=10)
        messages: list[dict] = []
        for t in prior:
            if t["role"] not in {"user", "assistant"}:
                continue
            messages.append({"role": t["role"], "content": t["content"]})

        prefix = ""
        if as_of:
            prefix = f"[as_of={as_of}] "
        messages.append({"role": "user", "content": prefix + user_message})
        return messages


def _summarize(result: Any) -> str:
    try:
        s = json.dumps(result, ensure_ascii=False)
    except Exception:  # noqa: BLE001
        s = str(result)
    return s[:240]
