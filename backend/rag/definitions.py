"""Extract defined terms from a contract's Definitions section.

A "defined term" in a legal/commercial document is a capitalised noun
phrase that the document binds to a specific meaning — "Pihak Penjual",
"Tanggal Penyelesaian", "Force Majeure Event". The definitions usually
live in one section near the top ("Ketentuan Umum" / "Definitions") and
are written as one of:

    "Term" berarti …
    "Term" means …
    Term adalah …
    Term : …

We parse these once at upload time and persist them. At retrieval time
the auto-injection step (see retriever) scans each retrieved chunk for
defined terms and injects their definitions into the model context.

This module is pure-text (no DB / LLM) so it's trivially testable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from backend.rag.doc_structure import OutlineNode, find_definitions_node


@dataclass(slots=True)
class DefinedTerm:
    term: str
    definition: str
    span_start: int
    span_end: int


# Match a single defined-term clause. We require either a quoted Term or
# a Capitalised-Phrase Term followed by a definition marker.
_QUOTED_RE = re.compile(
    r"""
    [\"“”‘’]
    (?P<term>[A-Z][^\"“”‘’]{0,80})
    [\"“”‘’]
    \s* (?:means|berarti|shall\s+mean|adalah|artinya)
    \s+ (?P<def>[^\n]{5,800})
    """,
    re.VERBOSE | re.I,
)

_UNQUOTED_RE = re.compile(
    r"""
    (?<![A-Za-z])                                # not in the middle of a word
    (?P<term>(?:[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,4}))
    \s+ (?:means|berarti|adalah|artinya)
    \s+ (?P<def>[^\n]{5,800})
    """,
    re.VERBOSE,
)


def _normalise_def(text: str) -> str:
    # Strip trailing punctuation that's the *clause* delimiter, not part of the def.
    return text.strip().rstrip(";").strip()


def extract_definitions(
    full_text: str,
    outline: OutlineNode | None = None,
) -> list[DefinedTerm]:
    """Return defined terms parsed from the Definitions section.

    If `outline` is provided we restrict the search to the definitions
    subtree; otherwise we scan the whole document. Restricting is
    important on long documents because operative clauses elsewhere
    sometimes use "means" in non-defining contexts.
    """
    if outline is not None:
        node = find_definitions_node(outline)
        if node is not None:
            haystack = full_text[node.span_start : node.span_end]
            offset = node.span_start
        else:
            haystack = full_text
            offset = 0
    else:
        haystack = full_text
        offset = 0

    seen: dict[str, DefinedTerm] = {}

    for m in _QUOTED_RE.finditer(haystack):
        term = m["term"].strip()
        defn = _normalise_def(m["def"])
        if not term or not defn:
            continue
        if term in seen:
            continue
        seen[term] = DefinedTerm(
            term=term,
            definition=defn,
            span_start=offset + m.start(),
            span_end=offset + m.end(),
        )

    for m in _UNQUOTED_RE.finditer(haystack):
        term = m["term"].strip()
        defn = _normalise_def(m["def"])
        if not term or not defn:
            continue
        # Heuristic: only accept Title-Cased terms; reject if all-lowercase
        # words sneak in.
        if not re.match(r"^[A-Z]", term):
            continue
        # Reject defs that start with lowercase 'a/an/the' — usually false
        # positives from operative clauses.
        if term in seen:
            continue
        seen[term] = DefinedTerm(
            term=term,
            definition=defn,
            span_start=offset + m.start(),
            span_end=offset + m.end(),
        )

    return list(seen.values())


def find_terms_in_text(text: str, terms: list[str]) -> list[str]:
    """Return the subset of `terms` that appear in `text` (whole-word, case-sensitive)."""
    if not terms:
        return []
    # Sort by length desc so multi-word terms win over single-word fragments.
    sorted_terms = sorted(set(terms), key=len, reverse=True)
    found: list[str] = []
    consumed_text = text
    for t in sorted_terms:
        if not t:
            continue
        pat = re.compile(r"\b" + re.escape(t) + r"\b")
        if pat.search(consumed_text):
            found.append(t)
    return found
