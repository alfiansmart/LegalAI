"""LLMClient facade — Anthropic-shaped API over three backends.

The shape mimics the Anthropic SDK on purpose: existing call sites do

    client = AsyncAnthropic(api_key=...)
    resp = await client.messages.create(
        model=settings.anthropic_model_default,
        max_tokens=4096,
        system=system_blocks,
        messages=messages,
        tools=tools,
    )
    for block in resp.content:
        if block.type == "text": ...
        elif block.type == "tool_use": ...

Switching providers means swapping the `AsyncAnthropic(...)` line for
`get_client()`. The rest stays put because `client.messages.create(...)`
returns the same shape regardless of who served the request.

Model resolution: the tier-keywords "default" and "fast" auto-resolve
to whichever model the active provider has configured for that tier.
Pass a literal model name to override.
"""
from __future__ import annotations

from typing import Any, Protocol

from backend.llm.types import LLMResponse

# `backend.config` is imported lazily so the LLM module stays
# importable in test environments without pydantic.


class _MessagesAPI(Protocol):
    async def create(self, **kwargs: Any) -> LLMResponse: ...


class LLMClient(Protocol):
    """Anthropic-compatible client surface."""

    messages: _MessagesAPI


def get_client() -> LLMClient:
    """Return a client for the active provider.

    Cheap to call — instances are stateless apart from their underlying
    HTTP client. Caching is left to provider implementations.
    """
    from backend.config import get_settings

    settings = get_settings()
    provider = settings.llm_provider
    if provider == "anthropic":
        from backend.llm.anthropic_provider import AnthropicClient

        return AnthropicClient()
    if provider in {"azure", "openai", "openrouter", "ollama"}:
        # Four OpenAI-Chat-Completions-shaped backends share one
        # translation layer; they differ only in client construction.
        from backend.llm.openai_provider import OpenAILikeClient

        return OpenAILikeClient(flavor=provider)
    raise ValueError(f"unknown llm provider {provider!r}")


def resolve_model(name_or_tier: str) -> str:
    """Translate the tier keywords 'default' / 'fast' into a provider-
    specific model name. Any other input is returned unchanged so
    explicit overrides still work."""
    from backend.config import get_settings

    settings = get_settings()
    if name_or_tier == "default":
        return settings.llm_model_default()
    if name_or_tier == "fast":
        return settings.llm_model_fast()
    return name_or_tier
