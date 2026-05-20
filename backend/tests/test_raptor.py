"""Tests for the pure-Python pieces of the RAPTOR builder.

The DB-touching paths (build_corpus_tree / build_document_tree) need a
real Postgres+pgvector and are exercised via integration tests. Here we
verify the small helpers that affect tree shape.
"""
from backend.rag.raptor import _outline_level_to_raptor


def test_outline_level_to_raptor_caps_at_known_levels():
    # Outline depth 1 (BAB / Section) -> RAPTOR level 2 (bab band).
    assert _outline_level_to_raptor(1) == 2
    # Depth 2 (Bagian / sub-section) -> RAPTOR level 1.
    assert _outline_level_to_raptor(2) == 1
    # Depth 3+ (Paragraf / Pasal / deeper) -> RAPTOR leaf (0).
    assert _outline_level_to_raptor(3) == 0
    assert _outline_level_to_raptor(4) == 0
    assert _outline_level_to_raptor(7) == 0


def test_outline_level_to_raptor_zero_is_bab_band():
    # A root-level outline node still belongs in the bab band.
    assert _outline_level_to_raptor(0) == 2
