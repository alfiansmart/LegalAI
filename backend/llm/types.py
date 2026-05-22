"""Provider-agnostic response types.

The harness was originally written against Anthropic's response shape:
`response.content` is a list of blocks, each either text (`.type ==
"text"`, `.text`) or a tool use (`.type == "tool_use"`, `.id`, `.name`,
`.input`). The OpenAI provider translates its `chat.completions`
output into the same shape via these dataclasses so callers don't
need to branch on provider.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(slots=True)
class TextBlock:
    text: str
    type: Literal["text"] = "text"


@dataclass(slots=True)
class ToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]
    type: Literal["tool_use"] = "tool_use"


ContentBlock = TextBlock | ToolUseBlock


@dataclass(slots=True)
class LLMResponse:
    """Anthropic-compatible response envelope.

    `stop_reason` follows Anthropic's vocabulary:
      - "end_turn"        — model finished naturally
      - "tool_use"        — model is asking us to invoke a tool
      - "max_tokens"      — model truncated against max_tokens
      - "stop_sequence"   — hit a configured stop sequence
    """

    content: list[ContentBlock] = field(default_factory=list)
    stop_reason: str = "end_turn"
    model: str | None = None
    raw: Any = None  # the underlying provider response, for debug
