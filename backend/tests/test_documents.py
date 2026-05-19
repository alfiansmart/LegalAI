from backend.documents import redline


def test_redline_detects_inserts_and_deletes():
    base = "satu\ndua\ntiga\n"
    head = "satu\ndua-baru\ntiga\nempat\n"
    hunks = redline.diff(base, head)
    kinds = {h.kind for h in hunks}
    assert "equal" in kinds
    assert "replace" in kinds or ("insert" in kinds and "delete" in kinds)
    u = redline.unified(base, head)
    assert "+dua-baru" in u or "+dua-baru\n" in u
    assert "+empat" in u


def test_redline_identical_only_equal():
    base = "alpha\nbeta\n"
    hunks = redline.diff(base, base)
    assert all(h.kind == "equal" for h in hunks)
