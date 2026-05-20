"""Tests for the token issue/verify helpers.

Pure-function — no DB needed. Verifies that:
  - tokens are random and unique across calls
  - the stored hash is the SHA-256 of the raw token
  - verify_token() rejects the wrong token, accepts the right one
"""
from backend.auth.tokens import hash_token, issue_token, verify_token


def test_issue_token_returns_distinct_raw_and_hash():
    raw, h = issue_token()
    assert raw and h
    assert raw != h
    assert hash_token(raw) == h


def test_issue_token_is_unique():
    raw1, _ = issue_token()
    raw2, _ = issue_token()
    assert raw1 != raw2


def test_verify_accepts_correct_token():
    raw, h = issue_token()
    assert verify_token(raw, h)


def test_verify_rejects_wrong_token():
    raw, h = issue_token()
    other, _ = issue_token()
    assert not verify_token(other, h)


def test_verify_rejects_empty_inputs():
    raw, h = issue_token()
    assert not verify_token("", h)
    assert not verify_token(raw, "")
    assert not verify_token("", "")


def test_hash_token_is_deterministic():
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("abd")
