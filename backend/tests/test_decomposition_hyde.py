"""Tests for the offline fallback paths of decomposition and HyDE.

The LLM-driven path needs ANTHROPIC_API_KEY; in CI/dev we verify the
no-key path returns sensible defaults so callers don't crash.
"""
import asyncio

from backend.rag import decomposition, hyde


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_decompose_without_key_returns_original():
    out = _run(
        decomposition.decompose(
            "Apa syarat sah perjanjian dan bagaimana dampaknya pada B2B?"
        )
    )
    # No key in test env → identity decomposition.
    assert out == ["Apa syarat sah perjanjian dan bagaimana dampaknya pada B2B?"]


def test_decompose_empty_returns_empty_list():
    assert _run(decomposition.decompose("")) == []


def test_hyde_without_key_returns_query():
    assert _run(hyde.hypothetical_answer("apa itu PKWT?")) == "apa itu PKWT?"
