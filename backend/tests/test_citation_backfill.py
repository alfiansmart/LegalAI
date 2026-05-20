"""Tests for the citation-kind inference layer of citation_backfill.

The DB-touching paths (backfill_for_peraturan / backfill_all) need a
live Postgres+pgvector and are exercised via integration tests. Here we
verify the pure-text kind-inference rules — the part that decides
whether a Pasal reference is REFERS, AMENDS, REPEALS, IMPLEMENTS, or
DASAR_HUKUM based on the surrounding text window.
"""
from backend.ingest.citation_backfill import _extract_refs_with_kind, _infer_kind


def test_default_kind_is_refers():
    assert _infer_kind("...lihat Pasal 5 KUHPerdata...") == "refers"


def test_amend_verb_promotes_to_amends():
    assert _infer_kind("Peraturan ini mengubah Pasal 5 UU 13/2003.") == "amends"
    assert _infer_kind("Pasal 5 diubah sebagai berikut: ...") == "amends"


def test_repeal_verb_promotes_to_repeals():
    assert _infer_kind("Pasal 5 UU 13/2003 dicabut dan tidak berlaku.") == "repeals"
    assert _infer_kind("Mencabut Pasal 5 UU 13/2003.") == "repeals"


def test_dasar_hukum_marker():
    assert _infer_kind("Mengingat Pasal 5 UUD 1945, ...") == "dasar_hukum"
    assert _infer_kind("Berdasarkan Pasal 5 KUHPerdata, ...") == "dasar_hukum"


def test_implementation_marker():
    assert _infer_kind("Peraturan pelaksana dari Pasal 5 UU 13/2003.") == "implements"


def test_extract_refs_with_kind_tags_each_ref():
    text = (
        "Mengingat Pasal 27 UUD 1945, peraturan ini mengubah Pasal 5 UU 13/2003 "
        "dan mencabut Pasal 6 UU 13/2003."
    )
    refs = _extract_refs_with_kind(text)
    kinds = [k for _, k in refs]
    assert "dasar_hukum" in kinds  # Pasal 27 UUD 1945
    assert "amends" in kinds  # Pasal 5 UU 13/2003
    assert "repeals" in kinds  # Pasal 6 UU 13/2003


def test_no_refs_returns_empty():
    assert _extract_refs_with_kind("hanya kalimat biasa tanpa rujukan pasal") == []
