"""Provider-agnostic LLM client.

Three providers are supported, picked by `Settings.llm_provider`:
  - `anthropic`   — direct passthrough to anthropic.AsyncAnthropic
  - `azure`       — Azure OpenAI deployment via the OpenAI SDK
  - `openrouter`  — OpenRouter's OpenAI-compatible endpoint

The facade exposes a single client object that quacks like
`AsyncAnthropic`: `client.messages.create(model=, messages=, system=,
tools=, max_tokens=)` and a response object with `.content[]`
(text + tool_use blocks) and `.stop_reason`. Existing call sites
that previously instantiated `AsyncAnthropic(api_key=…)` now call
`get_client()` instead — the rest of their code is unchanged.

Tool-use translation: Anthropic's `tool_use` blocks and OpenAI's
`tool_calls` field have different shapes; the OpenAI provider
translates both directions so the harness sees the Anthropic shape
regardless of who's serving the request.

Prompt-caching `cache_control` marks are stripped silently when
talking to OpenAI-style providers (they have no equivalent control
surface) — the prompt still works, just without the caching benefit.
Model-tier resolution: pass `model="default"` or `model="fast"` to
auto-pick the right model name for the active provider, or pass an
explicit provider-specific model string.
"""
from __future__ import annotations

from backend.llm.client import LLMClient, get_client
from backend.llm.types import LLMResponse, TextBlock, ToolUseBlock

__all__ = ["LLMClient", "LLMResponse", "TextBlock", "ToolUseBlock", "get_client"]
