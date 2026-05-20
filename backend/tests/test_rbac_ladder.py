"""Tests for the matter-role ladder ordering used by require_matter_access."""
from backend.auth.identity import _rank


def test_ladder_is_strictly_increasing():
    assert _rank("viewer") < _rank("reviewer") < _rank("editor") < _rank("owner")


def test_unknown_role_ranks_below_viewer():
    assert _rank("guest") == -1
    assert _rank("") == -1


def test_rank_idempotent_on_known_roles():
    for r in ["viewer", "reviewer", "editor", "owner"]:
        assert _rank(r) == _rank(r)


def test_ranks_have_distinct_values():
    ranks = {_rank(r) for r in ["viewer", "reviewer", "editor", "owner"]}
    assert len(ranks) == 4
