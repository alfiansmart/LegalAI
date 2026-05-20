"""Tests for the concept-graph extractor's offline behaviour."""
import asyncio

from backend.rag.concept_graph import extract_concepts_for_document


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_empty_text_is_noop():
    # Empty text should return 0 without touching the DB or LLM.
    assert _run(extract_concepts_for_document(99999, "")) == 0


def test_without_api_key_is_noop():
    # In the test env there's no ANTHROPIC_API_KEY; extractor short-circuits.
    assert _run(extract_concepts_for_document(99999, "Some real-looking contract text.")) == 0
