"""OpenAI-compatible provider (OpenAI / Azure OpenAI / OpenRouter / Ollama).

Translates Anthropic-shaped requests to OpenAI Chat Completions and
back, so existing call sites can swap provider via env var without
any code change. All four flavours share the translation layer; they
differ only in client construction:

  - `openai`     — AsyncOpenAI(api_key) — vanilla api.openai.com.
  - `azure`      — AsyncAzureOpenAI(api_key, endpoint, api_version),
                    `model=` is the *deployment name*.
  - `openrouter` — AsyncOpenAI(api_key, base_url=openrouter), model
                    strings like "anthropic/claude-3.5-sonnet". Adds
                    HTTP-Referer + X-Title attribution headers.
  - `ollama`     — AsyncOpenAI(base_url=ollama, api_key="ollama"),
                    model strings like "qwen2.5:14b". No real key
                    needed (Ollama runs locally) but the SDK insists
                    on a non-empty value.

Caveats per flavour:
  - Ollama models vary widely in tool-use support. Newer models
    (qwen2.5, qwen2.5-coder, llama3.1) handle OpenAI-format tools.
    Older ones may ignore the `tools` parameter — verify before
    promoting Ollama to your default provider.
  - Ollama's context window is whatever the model declares (often
    4-32K); LegalAI's long-doc CAG fallback caps at 150K. Trim the
    matter's documents or stick with chunked retrieval on small-window
    local models.

Translation rules:

  Anthropic                          → OpenAI
  ─────────────────────────────────────────────────────────────
  system: str | list[block]          → system message at the start
                                        of `messages` (cache_control
                                        stripped)
  messages: [{role, content[]}]      → flatten content blocks; text
                                        blocks join into a string;
                                        tool_use → assistant
                                        .tool_calls[]; tool_result →
                                        a separate {role: "tool"}
                                        message
  tools: [{name, description,        → [{type: "function",
          input_schema}]                function: {name, description,
                                        parameters}}]
  cache_control marks                → stripped (no OpenAI equivalent)

  OpenAI response                    → Anthropic-shape LLMResponse
  ─────────────────────────────────────────────────────────────
  message.content (str|None)         → TextBlock (if non-empty)
  message.tool_calls[]               → ToolUseBlock(id, name,
                                        input=json.loads(arguments))
  finish_reason                      → stop_reason
    "stop"              → "end_turn"
    "tool_calls"        → "tool_use"
    "length"            → "max_tokens"
    "content_filter"    → "stop_sequence"

Tool-arguments edge case: OpenAI returns `arguments` as a JSON-encoded
string; we parse it into a dict so downstream code sees the same shape
as Anthropic's pre-parsed `input` field.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Literal

from backend.llm.types import LLMResponse, TextBlock, ToolUseBlock

# `backend.config` and `backend.llm.client` are imported lazily inside
# the request-handling methods so this module stays importable in test
# environments that don't ship pydantic.

_log = logging.getLogger(__name__)


_STOP_MAP = {
    "stop": "end_turn",
    "tool_calls": "tool_use",
    "function_call": "tool_use",
    "length": "max_tokens",
    "content_filter": "stop_sequence",
}


class OpenAILikeClient:
    def __init__(
        self, *, flavor: Literal["openai", "azure", "openrouter", "ollama"]
    ) -> None:
        self.flavor = flavor
        self.messages = _MessagesAPI(flavor=flavor)


class _MessagesAPI:
    def __init__(
        self, *, flavor: Literal["openai", "azure", "openrouter", "ollama"]
    ) -> None:
        self.flavor = flavor

    async def create(self, **kwargs: Any) -> LLMResponse:
        from backend.config import get_settings
        from backend.llm.client import resolve_model

        settings = get_settings()
        model = resolve_model(kwargs.pop("model", "default"))
        max_tokens = kwargs.pop("max_tokens", 2048)
        anthropic_system = kwargs.pop("system", None)
        anthropic_messages = kwargs.pop("messages", [])
        anthropic_tools = kwargs.pop("tools", None)
        # Other kwargs we silently ignore for the OpenAI path (e.g.
        # `temperature`) only show up in our codebase via Anthropic
        # defaults; pass through anything we recognise.
        temperature = kwargs.pop("temperature", None)

        oa_messages = _translate_messages(anthropic_system, anthropic_messages)
        oa_tools = _translate_tools(anthropic_tools) if anthropic_tools else None

        client = _build_client(self.flavor, settings)
        try:
            call_kwargs: dict[str, Any] = {
                "model": model,
                "messages": oa_messages,
                "max_tokens": max_tokens,
            }
            if oa_tools is not None:
                call_kwargs["tools"] = oa_tools
            if temperature is not None:
                call_kwargs["temperature"] = temperature
            if self.flavor == "openrouter":
                # OpenRouter's recommended provider-attribution headers.
                call_kwargs["extra_headers"] = {
                    "HTTP-Referer": settings.openrouter_referer,
                    "X-Title": settings.openrouter_title,
                }
            elif self.flavor == "ollama":
                # Many Ollama models don't yet implement OpenAI's
                # `tools` parameter; passing it returns an error. We
                # let the call go through unchanged — admins picking
                # Ollama should set their default model to one that
                # supports tools (qwen2.5, llama3.1, …) or use the
                # workspace's task buttons (which call skills directly
                # and don't rely on the LLM tool loop).
                pass
            raw = await client.chat.completions.create(**call_kwargs)
        except Exception as e:  # noqa: BLE001
            _log.warning("openai-like create failed: %s", e)
            raise
        return _translate_response(raw, model=model)


# ---------------------------------------------------------------------------
# Client construction
# ---------------------------------------------------------------------------


def _build_client(flavor: str, settings):
    # Validate configuration *before* importing the openai SDK so a
    # missing-key error surfaces with a clear message even in
    # environments that haven't installed the package yet.
    if flavor == "openai":
        if not settings.openai_api_key:
            raise RuntimeError(
                "OpenAI selected but OPENAI_API_KEY is not set. Set the env "
                "var, or switch LLM_PROVIDER (anthropic / azure / openrouter "
                "/ ollama)."
            )
    elif flavor == "azure":
        if not (settings.azure_openai_api_key and settings.azure_openai_endpoint):
            raise RuntimeError(
                "Azure OpenAI selected but AZURE_OPENAI_API_KEY / "
                "AZURE_OPENAI_ENDPOINT are not set."
            )
    elif flavor == "openrouter":
        if not settings.openrouter_api_key:
            raise RuntimeError(
                "OpenRouter selected but OPENROUTER_API_KEY is not set."
            )
    elif flavor == "ollama":
        pass  # no credential to validate
    else:
        raise ValueError(f"unsupported openai flavour {flavor!r}")

    from openai import AsyncAzureOpenAI, AsyncOpenAI

    if flavor == "openai":
        kwargs: dict[str, Any] = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        if settings.openai_organization:
            kwargs["organization"] = settings.openai_organization
        return AsyncOpenAI(**kwargs)
    if flavor == "azure":
        return AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
        )
    if flavor == "openrouter":
        return AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )
    # ollama — runs locally, doesn't authenticate; the SDK demands a
    # non-empty api_key so we pass the sentinel.
    return AsyncOpenAI(
        api_key=settings.ollama_api_key or "ollama",
        base_url=settings.ollama_base_url,
    )


# ---------------------------------------------------------------------------
# Request translation: Anthropic → OpenAI
# ---------------------------------------------------------------------------


def _translate_messages(system: Any, anthropic_messages: list[dict]) -> list[dict]:
    out: list[dict] = []

    # System: anthropic accepts either a string or a list of content
    # blocks (with optional cache_control). OpenAI expects a single
    # system message with a string body.
    if system is not None:
        system_text = _system_to_text(system)
        if system_text:
            out.append({"role": "system", "content": system_text})

    for msg in anthropic_messages:
        role = msg.get("role")
        content = msg.get("content")
        if role == "user":
            user_blocks = _normalise_content(content)
            text_parts: list[str] = []
            tool_results: list[dict] = []
            for b in user_blocks:
                btype = b.get("type")
                if btype == "text":
                    text_parts.append(b.get("text", ""))
                elif btype == "tool_result":
                    tool_results.append(
                        {
                            "role": "tool",
                            "tool_call_id": b.get("tool_use_id", ""),
                            "content": _stringify(b.get("content")),
                        }
                    )
            if text_parts:
                out.append({"role": "user", "content": "\n\n".join(text_parts)})
            out.extend(tool_results)
        elif role == "assistant":
            asst_blocks = _normalise_content(content)
            text_parts = []
            tool_calls: list[dict] = []
            for b in asst_blocks:
                btype = b.get("type")
                if btype == "text":
                    text_parts.append(b.get("text", ""))
                elif btype == "tool_use":
                    tool_calls.append(
                        {
                            "id": b.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": b.get("name", ""),
                                "arguments": json.dumps(b.get("input", {}) or {}),
                            },
                        }
                    )
            msg_out: dict[str, Any] = {"role": "assistant"}
            # OpenAI requires `content` to be present even when null.
            msg_out["content"] = "\n\n".join(text_parts) if text_parts else None
            if tool_calls:
                msg_out["tool_calls"] = tool_calls
            out.append(msg_out)
        else:
            # Unknown role — pass through as-is, content stringified.
            out.append({"role": role or "user", "content": _stringify(content)})
    return out


def _system_to_text(system: Any) -> str:
    if isinstance(system, str):
        return system
    if isinstance(system, list):
        parts: list[str] = []
        for b in system:
            if isinstance(b, dict) and b.get("type") == "text":
                parts.append(b.get("text", ""))
            elif isinstance(b, str):
                parts.append(b)
        return "\n\n".join(p for p in parts if p)
    return ""


def _normalise_content(content: Any) -> list[dict]:
    """Anthropic accepts content as either a string or a list of blocks.
    We always return a list of blocks."""
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        out: list[dict] = []
        for b in content:
            if isinstance(b, dict):
                out.append(b)
            elif isinstance(b, str):
                out.append({"type": "text", "text": b})
        return out
    return []


def _stringify(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text":
                parts.append(b.get("text", ""))
            elif isinstance(b, str):
                parts.append(b)
            else:
                parts.append(json.dumps(b, ensure_ascii=False))
        return "\n\n".join(parts)
    try:
        return json.dumps(content, ensure_ascii=False)
    except Exception:  # noqa: BLE001
        return str(content)


def _translate_tools(anthropic_tools: list[dict]) -> list[dict]:
    out: list[dict] = []
    for t in anthropic_tools:
        out.append(
            {
                "type": "function",
                "function": {
                    "name": t.get("name", ""),
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema")
                    or {"type": "object", "properties": {}},
                },
            }
        )
    return out


# ---------------------------------------------------------------------------
# Response translation: OpenAI → Anthropic shape
# ---------------------------------------------------------------------------


def _translate_response(raw: Any, *, model: str) -> LLMResponse:
    blocks: list[TextBlock | ToolUseBlock] = []
    stop_reason = "end_turn"
    try:
        choice = raw.choices[0]
    except (AttributeError, IndexError, TypeError):
        return LLMResponse(content=[], stop_reason="end_turn", model=model, raw=raw)

    finish = getattr(choice, "finish_reason", None)
    if finish in _STOP_MAP:
        stop_reason = _STOP_MAP[finish]

    msg = getattr(choice, "message", None)
    if msg is not None:
        text = getattr(msg, "content", None)
        if text:
            blocks.append(TextBlock(text=text))
        tool_calls = getattr(msg, "tool_calls", None) or []
        if tool_calls:
            # Anthropic uses "tool_use" stop_reason whenever any tool
            # call is present; mirror that even if finish_reason
            # disagrees.
            stop_reason = "tool_use"
        for tc in tool_calls:
            fn = getattr(tc, "function", None)
            if fn is None:
                continue
            args_raw = getattr(fn, "arguments", "") or ""
            try:
                args = json.loads(args_raw) if args_raw else {}
            except json.JSONDecodeError:
                # Tolerate model-emitted invalid JSON — pass an empty
                # input rather than crashing the loop.
                args = {}
            blocks.append(
                ToolUseBlock(
                    id=getattr(tc, "id", "") or "",
                    name=getattr(fn, "name", "") or "",
                    input=args,
                )
            )
    return LLMResponse(content=blocks, stop_reason=stop_reason, model=model, raw=raw)
