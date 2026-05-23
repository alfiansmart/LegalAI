"""Tests for `apply_suggestion` — the splice helper used when accepting
a track-changes Suggestion.

The function lives in `backend/documents/splice.py` and is intentionally
pure (no DB, no HTTP, no framework). These tests cover the validation
behaviour that the route handler relies on to avoid silent document
corruption when the document has been edited under a pending suggestion.
"""
import pytest

from backend.documents.splice import StaleSuggestionError, apply_suggestion


# ---------- Happy paths ----------------------------------------------------


def test_simple_replacement_in_middle():
    out = apply_suggestion(
        current="hello world",
        range_start=6,
        range_end=11,
        base_text="world",
        proposed_text="universe",
    )
    assert out == "hello universe"


def test_replacement_at_start():
    out = apply_suggestion(
        current="hello world",
        range_start=0,
        range_end=5,
        base_text="hello",
        proposed_text="halo",
    )
    assert out == "halo world"


def test_replacement_at_end():
    out = apply_suggestion(
        current="hello world",
        range_start=6,
        range_end=11,
        base_text="world",
        proposed_text="dunia",
    )
    assert out == "hello dunia"


def test_insert_style_with_empty_base_text():
    # range_start == range_end, base_text empty — insert at that point.
    out = apply_suggestion(
        current="Pasal 1\nPasal 2\n",
        range_start=8,
        range_end=8,
        base_text="",
        proposed_text="Pasal 1A\n",
    )
    assert out == "Pasal 1\nPasal 1A\nPasal 2\n"


def test_insert_at_doc_end_is_valid():
    current = "Pasal 1\nPasal 2\n"
    out = apply_suggestion(
        current=current,
        range_start=len(current),
        range_end=len(current),
        base_text="",
        proposed_text="Pasal 3\n",
    )
    assert out == "Pasal 1\nPasal 2\nPasal 3\n"


def test_replace_multi_line_clause():
    current = "Pasal 5\nIsi lama.\nPasal 6\n"
    out = apply_suggestion(
        current=current,
        range_start=8,
        range_end=17,
        base_text="Isi lama.",
        proposed_text="Isi baru yang lebih lengkap.",
    )
    assert out == "Pasal 5\nIsi baru yang lebih lengkap.\nPasal 6\n"


def test_empty_replacement_text_is_a_deletion():
    out = apply_suggestion(
        current="hello world",
        range_start=5,
        range_end=11,
        base_text=" world",
        proposed_text="",
    )
    assert out == "hello"


# ---------- Validation errors (stale suggestions) -------------------------


def test_range_end_beyond_doc_raises_stale():
    """The doc is now shorter than when the suggestion was created.
    Without this guard Python's slice would silently produce wrong
    output (`current[range_end:]` returns "" past the end)."""
    with pytest.raises(StaleSuggestionError) as exc:
        apply_suggestion(
            current="short",
            range_start=0,
            range_end=999,
            base_text="anything",
            proposed_text="replacement",
        )
    assert "no longer fits" in str(exc.value).lower() or "range" in str(exc.value).lower()


def test_negative_range_start_raises_stale():
    with pytest.raises(StaleSuggestionError):
        apply_suggestion(
            current="hello",
            range_start=-1,
            range_end=3,
            base_text="hel",
            proposed_text="x",
        )


def test_inverted_range_raises_stale():
    with pytest.raises(StaleSuggestionError):
        apply_suggestion(
            current="hello",
            range_start=4,
            range_end=2,
            base_text="lo",
            proposed_text="x",
        )


def test_base_text_drift_raises_stale():
    """Document was edited under the suggestion — text at the suggestion's
    range no longer matches what the AI quoted as base_text."""
    with pytest.raises(StaleSuggestionError) as exc:
        apply_suggestion(
            current="hello world",
            range_start=0,
            range_end=5,
            base_text="halo",  # AI saw "halo" but doc now has "hello"
            proposed_text="goodbye",
        )
    assert "no longer matches" in str(exc.value).lower() or "base_text" in str(exc.value)


def test_base_text_drift_case_mismatch_still_rejects():
    # The first 4 chars of "hello" are "hell" — exact equality, not
    # case-insensitive substring. Force the validator to be strict.
    with pytest.raises(StaleSuggestionError):
        apply_suggestion(
            current="hello world",
            range_start=0,
            range_end=4,
            base_text="HELL",
            proposed_text="x",
        )


def test_insert_past_doc_end_raises_stale():
    with pytest.raises(StaleSuggestionError):
        apply_suggestion(
            current="short",
            range_start=10,
            range_end=10,
            base_text="",
            proposed_text="x",
        )


def test_zero_width_replace_in_middle_with_matching_base_text():
    # Edge case: base_text is empty but range is a point not at the
    # end — should still be a valid insert.
    out = apply_suggestion(
        current="hello world",
        range_start=5,
        range_end=5,
        base_text="",
        proposed_text=",",
    )
    assert out == "hello, world"
