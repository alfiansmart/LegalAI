"""Tests for the defined-terms extractor."""
from backend.rag.definitions import extract_definitions, find_terms_in_text
from backend.rag.doc_structure import parse_structure


def test_quoted_terms_with_indonesian_marker():
    text = """\
Definitions

"Pihak Penjual" berarti PT Alpha Mandiri, sebuah perseroan terbatas.
"Pihak Pembeli" berarti PT Beta Sejahtera.
"""
    terms = extract_definitions(text)
    by_name = {t.term: t for t in terms}
    assert "Pihak Penjual" in by_name
    assert "Pihak Pembeli" in by_name
    assert "PT Alpha Mandiri" in by_name["Pihak Penjual"].definition


def test_quoted_terms_with_english_marker():
    text = """\
Definitions

"Cure Period" means the thirty (30) day period within which a breaching party may cure.
"""
    terms = extract_definitions(text)
    assert any(t.term == "Cure Period" for t in terms)


def test_restricted_to_definitions_section_when_outline_provided():
    text = """\
Definitions

"Pihak Penjual" berarti PT Alpha.

Section 1. Operations
The Cure Period means the time allowed for fixing breaches under normal circumstances.
"""
    outline = parse_structure(text)
    terms = extract_definitions(text, outline=outline)
    by_name = {t.term: t for t in terms}
    # "Pihak Penjual" lives in Definitions and is captured.
    assert "Pihak Penjual" in by_name
    # "Cure Period" lives in Operations — should NOT be captured when we
    # restrict to the Definitions section.
    assert "Cure Period" not in by_name


def test_find_terms_in_text_matches_whole_words():
    found = find_terms_in_text(
        "Pihak Penjual akan menyerahkan barang sebelum tanggal penyelesaian.",
        ["Pihak Penjual", "Pihak Pembeli", "Tanggal Penyelesaian"],
    )
    assert "Pihak Penjual" in found
    assert "Pihak Pembeli" not in found
