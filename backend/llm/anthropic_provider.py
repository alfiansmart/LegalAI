"""Anthropic provider — direct passthrough.

The whole reason for the LLMResponse dataclass shape was to mirror
Anthropic's response, so this provider mostly just hands the SDK's
response back through. We do still wrap it in our LLMResponse so
type-checkers (and the openai provider's translation tests) work
against a single shape.
"""
from __future__ import annotations

from typing import Any

from backend.llm.types import LLMResponse, TextBlock, ToolUseBlock

# `backend.config` and `backend.llm.client` are imported lazily so this
# module stays importable in test environments without pydantic.


class AnthropicClient:
    """Mirrors AsyncAnthropic's `client.messages.create(...)` surface."""

    def __init__(self) -> None:
        self.messages = _MessagesAPI()


class _MessagesAPI:
    async def create(self, **kwargs: Any) -> LLMResponse:
        from anthropic import AsyncAnthropic

        from backend.config import get_settings
        from backend.llm.client import resolve_model

        settings = get_settings()
        api_key = settings.anthropic_api_key
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set — set it or switch LLM_PROVIDER to "
                "'azure' / 'openrouter' with the matching env vars."
            )
        client = AsyncAnthropic(api_key=api_key)
        # Translate model tier shorthand ("default" / "fast") to a
        # concrete model name for the active provider.
        if "model" in kwargs:
            kwargs["model"] = resolve_model(kwargs["model"])
        resp = await client.messages.create(**kwargs)
        return _to_llm_response(resp)


def _to_llm_response(raw: Any) -> LLMResponse:
    blocks: list[TextBlock | ToolUseBlock] = []
    for b in raw.content:
        btype = getattr(b, "type", None)
        if btype == "text":
            blocks.append(TextBlock(text=getattr(b, "text", "")))
        elif btype == "tool_use":
            blocks.append(
                ToolUseBlock(
                    id=getattr(b, "id", ""),
                    name=getattr(b, "name", ""),
                    input=dict(getattr(b, "input", {}) or {}),
                )
            )
    return LLMResponse(
        content=blocks,
        stop_reason=getattr(raw, "stop_reason", "end_turn") or "end_turn",
        model=getattr(raw, "model", None),
        raw=raw,
    )
