"""Tests for the canonical hierarchy mapping from UU 12/2011.

The hierarchy module is the single source of truth for the lex
superior ordering. The retriever boosts scores by it, the agent
explains conflicts by it, and downstream features that compare two
peraturan ("which one wins?") rely on it.
"""
from backend.legal.hierarchy import (
    hierarchy_boost,
    is_article_7,
    is_article_8,
    is_higher_than,
    level_of,
)


def test_article_7_levels_strictly_increase():
    # UUD < TapMPR < UU/Perppu < PP < Perpres < Perda Provinsi < Perda Kab
    assert level_of("UUD") == 1
    assert level_of("TapMPR") == 2
    assert level_of("UU") == 3
    assert level_of("Perppu") == 3
    assert level_of("PP") == 4
    assert level_of("Perpres") == 5
    assert level_of("PerdaProv") == 7
    assert level_of("PerdaKab") == 8


def test_kitab_treated_as_uu_level():
    # KUHP / KUHPerdata / KUHAP are interpreted at UU tier even though
    # they originate as Staatsblad.
    assert level_of("KUHP") == 3
    assert level_of("KUHPerdata") == 3
    assert level_of("KUHAP") == 3


def test_article_8_bodies_slot_between_perpres_and_perda():
    for jenis in ["Permen", "POJK", "PBI", "PADG", "Perma", "PerMK", "PerKPU", "Perka"]:
        assert 5 < level_of(jenis) < 8, jenis


def test_putusan_levels():
    # Putusan MK has constitutional review weight (UU-tier).
    assert level_of("PutusanMK") == 3
    # Putusan MA is treated as persuasive precedent on regulation review.
    assert level_of("PutusanMA") == 6


def test_unknown_jenis_lands_at_bottom():
    assert level_of(None) == 9
    assert level_of("FantasyDecree") == 9


def test_is_higher_than_obeys_lex_superior():
    assert is_higher_than("UUD", "UU")
    assert is_higher_than("UU", "PP")
    assert is_higher_than("PP", "Perpres")
    assert is_higher_than("Perpres", "Permen")
    assert not is_higher_than("Permen", "PP")
    # Same-level pairs are neither higher nor lower.
    assert not is_higher_than("UU", "Perppu")
    assert not is_higher_than("Perppu", "UU")


def test_hierarchy_boost_decreases_with_level():
    # Higher authority → larger boost; bottom levels round to ~0.
    levels_desc = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    boosts = [hierarchy_boost(L) for L in levels_desc]
    assert all(boosts[i] >= boosts[i + 1] for i in range(len(boosts) - 1))
    assert boosts[0] > 0.0
    assert boosts[-1] == 0.0


def test_hierarchy_boost_handles_none():
    assert hierarchy_boost(None) == 0.0


def test_article_7_membership():
    for j in ["UUD", "TapMPR", "UU", "Perppu", "PP", "Perpres", "PerdaProv", "PerdaKab"]:
        assert is_article_7(j), j
    for j in ["Permen", "POJK", "Perma", "PutusanMK"]:
        assert not is_article_7(j), j


def test_article_8_membership():
    for j in ["Permen", "Perma", "SEMA", "PerMK", "PerKPU", "POJK", "PBI", "PADG", "Perka"]:
        assert is_article_8(j), j
    for j in ["UUD", "UU", "PP", "Perpres", "PerdaProv"]:
        assert not is_article_8(j), j
