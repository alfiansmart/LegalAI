"""Tests for the structure-aware chunker.

Key invariants:
  - Chunks are never split across Pasal/clause boundaries.
  - Every chunk carries a non-empty breadcrumb when the doc has structure.
  - A heading-less document still chunks via sentence windows.
"""
from backend.rag.chunker import chunk_document


def test_no_chunk_spans_two_pasal():
    text = """\
BAB I
KETENTUAN UMUM

Pasal 1
Klausa A dijelaskan di sini secara singkat saja.

Pasal 2
Klausa B menjelaskan kewajiban pihak pertama.

Pasal 3
Klausa C mengatur force majeure dan situasi luar biasa.
"""
    _, chunks = chunk_document(text)
    # Every chunk's text should contain exactly one Pasal heading or none
    # (if the chunk is purely body text under a single Pasal).
    for c in chunks:
        # Count Pasal-line occurrences inside the chunk body.
        count = sum(1 for ln in c.text.splitlines() if ln.strip().startswith("Pasal "))
        assert count <= 1, f"chunk spans multiple Pasal: {c.breadcrumb!r}\n{c.text!r}"


def test_breadcrumb_is_set_for_structured_docs():
    text = """\
BAB I
KETENTUAN UMUM

Pasal 1
Isi pasal satu.
"""
    _, chunks = chunk_document(text)
    assert chunks, "expected at least one chunk"
    assert all(c.breadcrumb for c in chunks)


def test_headingless_text_falls_back_to_sentence_windows():
    text = " ".join([f"Sentence number {i} contains substantive content." for i in range(60)])
    _, chunks = chunk_document(text, max_tokens=200, overlap_tokens=20)
    assert len(chunks) >= 2
    # No structure -> breadcrumb empty
    assert all(c.breadcrumb == "" for c in chunks)


def test_oversize_leaf_is_split_with_overlap():
    body = " ".join([f"Sentence {i}." for i in range(400)])  # forces split
    text = f"Pasal 1\n{body}"
    _, chunks = chunk_document(text, max_tokens=200, overlap_tokens=40)
    # Should produce more than one chunk, all under the same breadcrumb
    assert len(chunks) > 1
    assert all("Pasal 1" in c.breadcrumb for c in chunks)
