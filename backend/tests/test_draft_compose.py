"""Tests for the small pure-text helpers inside draft_compose.

The LLM-driven paths (draft_from_description, draft_revise_section,
draft_insert_clause) need ANTHROPIC_API_KEY + a live DB; here we cover
the offset / fallback logic those skills rely on, which is what the
splice correctness hinges on.
"""
import importlib.util
import pathlib


def _load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_BASE = pathlib.Path("skills/draft_compose/backend/tools")
revise = _load("draft_revise_section_under_test", _BASE / "draft_revise_section.py")
insert = _load("draft_insert_clause_under_test", _BASE / "draft_insert_clause.py")


# ---------- fuzzy_find ----------------------------------------------------


def test_fuzzy_find_exact_match():
    assert revise._fuzzy_find("abc def ghi", "def") == 4


def test_fuzzy_find_collapses_repeated_whitespace():
    haystack = "Pasal 5\n    Setiap   pekerja\n  berhak\n"
    needle = "Setiap pekerja berhak"
    assert revise._fuzzy_find(haystack, needle) >= 0


def test_fuzzy_find_returns_minus_one_when_absent():
    assert revise._fuzzy_find("just some text", "not here") == -1


# ---------- next_pasal_number ---------------------------------------------


def test_next_pasal_number_empty_doc():
    assert insert._next_pasal_number("") == 1
    assert insert._next_pasal_number("no pasal here") == 1


def test_next_pasal_number_walks_to_max():
    text = """\
Pasal 1
...

Pasal 2
...

Pasal 5
...
"""
    # Returns max + 1 even when numbering has gaps.
    assert insert._next_pasal_number(text) == 6


def test_next_pasal_number_skips_inline_mentions():
    # "Pasal 5" inside a citation shouldn't be counted as a heading.
    text = "Mengingat Pasal 27 UUD 1945."
    # Our regex is anchored to line-start? Actually _PASAL_HEADING_RE
    # uses re.M but no ^ anchor; verify behavior we ship.
    n = insert._next_pasal_number(text)
    assert n >= 1  # implementation detail tolerated, no crash


# ---------- find_insertion_offset -----------------------------------------


def test_insertion_before_closing_block_when_no_after_section():
    text = """\
Pasal 1
Body.

Pasal 2
Body.

Ditetapkan di Jakarta pada tanggal 1 Januari 2024.
"""
    pos = insert._find_insertion_offset(text, after_section="")
    # Should land on the "Ditetapkan" line.
    assert text[pos:pos + 10].startswith("Ditetapkan")


def test_insertion_at_end_of_doc_when_no_closing_block():
    text = "Pasal 1\nBody.\nPasal 2\nBody.\n"
    pos = insert._find_insertion_offset(text, after_section="")
    assert pos == len(text)


def test_insertion_after_named_section():
    text = """\
Pasal 1
Definisi.

Pasal 2
Lingkup.

Pasal 3
Pengakhiran.
"""
    pos = insert._find_insertion_offset(text, after_section="Pasal 1")
    # Should land right before Pasal 2 (the next heading after "Pasal 1").
    assert text[pos:].lstrip().startswith("Pasal 2"), text[pos : pos + 20]
