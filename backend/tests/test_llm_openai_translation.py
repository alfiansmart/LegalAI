"""Tests for the Anthropic ↔ OpenAI translation layer.

Pure-text — no HTTP. The end-to-end smoke (a real Azure/OpenRouter
request) needs network and is exercised manually.
"""
import json
from types import SimpleNamespace

from backend.llm import openai_provider as provider


# ---------- _translate_messages ---------------------------------------------


def test_string_system_becomes_first_system_message():
    out = provider._translate_messages("You are a lawyer.", [{"role": "user", "content": "Halo"}])
    assert out[0] == {"role": "system", "content": "You are a lawyer."}
    assert out[1]["role"] == "user"


def test_block_list_system_strips_cache_control_and_joins_text():
    system = [
        {"type": "text", "text": "Persona A.", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "Skill block B."},
    ]
    out = provider._translate_messages(system, [{"role": "user", "content": "halo"}])
    assert out[0]["role"] == "system"
    assert "Persona A." in out[0]["content"]
    assert "Skill block B." in out[0]["content"]


def test_user_content_blocks_concatenate_text():
    out = provider._translate_messages(
        None,
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Part 1"},
                    {"type": "text", "text": "Part 2"},
                ],
            }
        ],
    )
    assert out == [{"role": "user", "content": "Part 1\n\nPart 2"}]


def test_tool_result_block_becomes_tool_message():
    out = provider._translate_messages(
        None,
        [
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "toolu_1", "content": "answer"}
                ],
            }
        ],
    )
    assert out == [{"role": "tool", "tool_call_id": "toolu_1", "content": "answer"}]


def test_assistant_tool_use_becomes_tool_calls_with_json_string_args():
    out = provider._translate_messages(
        None,
        [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "thinking…"},
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "pasal_lookup",
                        "input": {"q": "1320"},
                    },
                ],
            }
        ],
    )
    assert out[0]["role"] == "assistant"
    assert out[0]["content"] == "thinking…"
    assert out[0]["tool_calls"][0]["id"] == "toolu_1"
    assert out[0]["tool_calls"][0]["function"]["name"] == "pasal_lookup"
    args = json.loads(out[0]["tool_calls"][0]["function"]["arguments"])
    assert args == {"q": "1320"}


# ---------- _translate_tools -----------------------------------------------


def test_translate_tools_wraps_in_function_envelope():
    tools = [
        {
            "name": "pasal_lookup",
            "description": "Look up a Pasal.",
            "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}},
        }
    ]
    out = provider._translate_tools(tools)
    assert out[0] == {
        "type": "function",
        "function": {
            "name": "pasal_lookup",
            "description": "Look up a Pasal.",
            "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
        },
    }


def test_translate_tools_defaults_empty_parameters_object():
    out = provider._translate_tools([{"name": "ping", "description": ""}])
    assert out[0]["function"]["parameters"] == {"type": "object", "properties": {}}


# ---------- _translate_response --------------------------------------------


def _fake_response(*, content, tool_calls, finish):
    msg = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(message=msg, finish_reason=finish)
    return SimpleNamespace(choices=[choice])


def test_response_text_only_returns_one_text_block_with_end_turn():
    raw = _fake_response(content="hello world", tool_calls=None, finish="stop")
    resp = provider._translate_response(raw, model="m")
    assert resp.stop_reason == "end_turn"
    assert len(resp.content) == 1
    assert resp.content[0].type == "text"
    assert resp.content[0].text == "hello world"


def test_response_with_tool_calls_emits_tool_use_blocks_and_correct_stop():
    tc = SimpleNamespace(
        id="call_42",
        function=SimpleNamespace(name="pasal_lookup", arguments='{"q":"1320"}'),
    )
    raw = _fake_response(content=None, tool_calls=[tc], finish="tool_calls")
    resp = provider._translate_response(raw, model="m")
    assert resp.stop_reason == "tool_use"
    assert len(resp.content) == 1
    assert resp.content[0].type == "tool_use"
    assert resp.content[0].id == "call_42"
    assert resp.content[0].name == "pasal_lookup"
    assert resp.content[0].input == {"q": "1320"}


def test_response_text_plus_tool_calls_marks_tool_use_stop():
    tc = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(name="x", arguments="{}"),
    )
    raw = _fake_response(content="ok, looking up", tool_calls=[tc], finish="tool_calls")
    resp = provider._translate_response(raw, model="m")
    types = [b.type for b in resp.content]
    assert "text" in types and "tool_use" in types
    assert resp.stop_reason == "tool_use"


def test_invalid_tool_arguments_json_yields_empty_input():
    tc = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(name="x", arguments="{not-json"),
    )
    raw = _fake_response(content=None, tool_calls=[tc], finish="tool_calls")
    resp = provider._translate_response(raw, model="m")
    assert resp.content[0].input == {}


def test_finish_reason_length_maps_to_max_tokens():
    raw = _fake_response(content="truncated…", tool_calls=None, finish="length")
    resp = provider._translate_response(raw, model="m")
    assert resp.stop_reason == "max_tokens"


def test_empty_response_safely_returns_empty_content():
    raw = SimpleNamespace(choices=[])
    resp = provider._translate_response(raw, model="m")
    assert resp.content == []
    assert resp.stop_reason == "end_turn"


# ---------- _stringify -----------------------------------------------------


def test_stringify_passthrough_string():
    assert provider._stringify("hello") == "hello"


def test_stringify_none_returns_empty():
    assert provider._stringify(None) == ""


def test_stringify_block_list_concatenates_text_blocks():
    blocks = [{"type": "text", "text": "A"}, {"type": "text", "text": "B"}]
    assert "A" in provider._stringify(blocks)
    assert "B" in provider._stringify(blocks)


def test_stringify_dict_becomes_json():
    out = provider._stringify({"k": 1})
    assert "k" in out


# ---------- end-to-end translation sanity ----------------------------------


def test_round_trip_assistant_tool_use_then_tool_result():
    """The harness's tool loop appends an assistant turn (with tool_use)
    and a user turn (with tool_result). Confirm both translate to the
    correct OpenAI shape in the right order."""
    msgs = [
        {"role": "user", "content": "Look up Pasal 1320."},
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "toolu_1", "name": "pasal_lookup", "input": {"q": "1320"}},
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "toolu_1", "content": "result text"},
            ],
        },
    ]
    out = provider._translate_messages("system", msgs)
    roles = [m["role"] for m in out]
    assert roles == ["system", "user", "assistant", "tool"]
    assert out[3]["tool_call_id"] == "toolu_1"
    assert out[3]["content"] == "result text"


# ---------- _build_client --------------------------------------------------


class _S:
    """Minimal Settings stand-in for client-construction tests."""

    def __init__(self, **kw):
        self.openai_api_key = None
        self.openai_base_url = None
        self.openai_organization = None
        self.azure_openai_api_key = None
        self.azure_openai_endpoint = None
        self.azure_openai_api_version = "2024-10-21"
        self.openrouter_api_key = None
        self.openrouter_base_url = "https://openrouter.ai/api/v1"
        self.ollama_api_key = "ollama"
        self.ollama_base_url = "http://localhost:11434/v1"
        for k, v in kw.items():
            setattr(self, k, v)


def test_build_openai_requires_api_key():
    import pytest

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        provider._build_client("openai", _S())


def test_build_azure_requires_endpoint_and_key():
    import pytest

    with pytest.raises(RuntimeError, match="AZURE_OPENAI"):
        provider._build_client("azure", _S(azure_openai_api_key="x"))
    with pytest.raises(RuntimeError, match="AZURE_OPENAI"):
        provider._build_client("azure", _S(azure_openai_endpoint="https://x"))


def test_build_openrouter_requires_key():
    import pytest

    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        provider._build_client("openrouter", _S())


def test_build_ollama_uses_sentinel_when_key_missing():
    """Ollama doesn't authenticate; the SDK insists on a non-empty
    key so we pass 'ollama' rather than asking the user to set one."""
    import pytest

    pytest.importorskip("openai")
    client = provider._build_client("ollama", _S(ollama_api_key=""))
    # We just verify the call returns a client; AsyncOpenAI's internals
    # are out of scope. The api_key was substituted internally.
    assert client is not None


def test_build_unknown_flavor_raises():
    import pytest

    with pytest.raises(ValueError, match="unsupported openai flavour"):
        provider._build_client("bogus", _S())
