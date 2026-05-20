"""Tests for the CRAG grader's offline (heuristic) path.

The LLM-graded path needs ANTHROPIC_API_KEY and network — we test
the score-threshold fallback that runs in dev / CI."""
import asyncio

from backend.rag.crag import Grade, Verdict, grade


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_no_hits_is_insufficient():
    g = _run(grade("apa itu PKWT?", []))
    assert g.verdict == Verdict.INSUFFICIENT
    assert g.refined_query == "apa itu PKWT?"


def test_low_top_score_is_insufficient():
    g = _run(grade("apa itu PKWT?", [{"score": 0.1, "teks": "irrelevant"}]))
    assert g.verdict == Verdict.INSUFFICIENT


def test_mid_top_score_is_partial():
    g = _run(grade("apa itu PKWT?", [{"score": 0.4, "teks": "marginal"}]))
    assert g.verdict == Verdict.PARTIAL


def test_high_top_score_is_sufficient():
    g = _run(grade("apa itu PKWT?", [{"score": 0.8, "teks": "good"}]))
    assert g.verdict == Verdict.SUFFICIENT


def test_verdict_is_str_enum():
    assert Grade(Verdict.SUFFICIENT, "ok").verdict.value == "sufficient"
