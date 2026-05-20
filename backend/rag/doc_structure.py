"""Parse an uploaded legal/contract document into a structural outline tree.

Indonesian legal documents and commercial contracts use a small set of
recurring heading patterns. We detect them with anchored line-start
regexes, then nest matches by their natural level via a stack.

Supported heading kinds (mapped to a base level):

    bab          (BAB I, BAB II)                level 1
    bagian       (Bagian Kesatu, Bagian Kedua)  level 2
    paragraf     (Paragraf 1)                   level 3
    pasal        (Pasal 1, Pasal 1A)            level 4
    ayat         ((1), (1a)) -- inline, skipped for outline
    section      (SECTION 1., Section 1)        level 1
    clause       (1., 1.1, 1.1.1) numbered      1 + dot_count
    schedule     (Lampiran A, Schedule 1)       level 1
    definitions  (Ketentuan Umum / Definitions) level 1

A mixed document (peraturan style + numbered clauses) parses fine
because the algorithm relies on absolute level numbers, not pattern
order.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class OutlineNode:
    kind: str
    ordinal: int
    title: str | None
    span_start: int
    span_end: int  # filled by parser; end = next heading's start or len(text)
    level: int
    children: list[OutlineNode] = field(default_factory=list)
    parent: OutlineNode | None = None

    def walk(self):
        yield self
        for ch in self.children:
            yield from ch.walk()

    def breadcrumb(self) -> str:
        parts: list[str] = []
        n: OutlineNode | None = self
        while n and n.parent is not None:
            label = (n.title or "").strip() or n.kind.title()
            parts.append(label)
            n = n.parent
        return " / ".join(reversed(parts))


# ---------- Heading patterns ----------
# Each pattern returns (match_obj, kind, base_level, title_extractor).
# The title_extractor takes the match and returns the visible heading text.

_ROMAN_RE = r"[IVXLCDM]+"
_ID_NUM_WORD = r"(?:Kesatu|Kedua|Ketiga|Keempat|Kelima|Keenam|Ketujuh|Kedelapan|Kesembilan|Kesepuluh|Kesebelas|Keduabelas)"

_BAB_RE = re.compile(
    rf"^[ \t]*BAB\s+(?P<n>{_ROMAN_RE}|\d+|[A-Z]+)\b[ \t]*(?P<title>.*)$",
    re.M,
)
_BAGIAN_RE = re.compile(
    rf"^[ \t]*Bagian\s+(?P<n>{_ID_NUM_WORD}|\d+)\b[ \t]*(?P<title>.*)$",
    re.M | re.I,
)
_PARAGRAF_RE = re.compile(r"^[ \t]*Paragraf\s+(?P<n>\d+)\b[ \t]*(?P<title>.*)$", re.M | re.I)
_PASAL_RE = re.compile(r"^[ \t]*Pasal\s+(?P<n>\d+[A-Z]?)\b[ \t]*(?P<title>.*)$", re.M)
_SECTION_RE = re.compile(
    r"^[ \t]*(?:SECTION|Section|Klausa|KLAUSA)\s+(?P<n>\d+(?:\.\d+)*)[.:]?[ \t]*(?P<title>.*)$",
    re.M,
)
_CLAUSE_RE = re.compile(
    r"^[ \t]*(?P<n>\d+(?:\.\d+){0,5})\.?[ \t]+(?P<title>[A-Z][^\n]{2,})$",
    re.M,
)
_SCHEDULE_RE = re.compile(
    r"^[ \t]*(?P<n>Lampiran|Schedule|Annex|Annexure)\s+(?P<id>[A-Z\d][A-Z\d\-]*)\b[ \t]*(?P<title>.*)$",
    re.M | re.I,
)
# Definitions section is detected as a TAG on existing structural nodes
# (find_definitions_node walks the tree looking for matching titles),
# rather than as a heading kind of its own. This avoids the case where
# "BAB I KETENTUAN UMUM" both opens BAB I and a separate definitions
# block, which breaks nesting.
_DEFINITIONS_TITLE_RE = re.compile(
    r"\b(Ketentuan\s+Umum|Definitions?|Definisi|Pengertian|Interpretasi|Interpretation)\b",
    re.I,
)

# Standalone definitions heading — only matched when the line is JUST
# the keyword (no BAB/Section/Pasal prefix). Used in contracts that have
# a bare `Definitions` section header.
_STANDALONE_DEFINITIONS_RE = re.compile(
    r"^[ \t]*(?P<title>Definitions?|Definisi|Interpretation|Interpretasi)\b[ \t]*:?[ \t]*$",
    re.M | re.I,
)


@dataclass
class _Hit:
    start: int
    end_of_heading_line: int
    kind: str
    level: int
    title: str
    ordinal_hint: str


def _next_line_title(text: str, after: int) -> tuple[str, int]:
    """Return (title-line-text, end-offset) if the next non-blank line looks
    like a heading title (short, mostly uppercase or Title Case). Else ("", after).

    Peraturan often format `BAB I` on one line with `KETENTUAN UMUM` directly
    below — we glue those together for a usable title.
    """
    i = after
    # Skip exactly one newline (the one that ended the heading line).
    while i < len(text) and text[i] in "\r\n":
        i += 1
    # Read the next line.
    nl = text.find("\n", i)
    if nl == -1:
        nl = len(text)
    line = text[i:nl].strip()
    if not line:
        return "", after
    # Heuristic: title line is short, no terminal period, mostly letters.
    if len(line) > 120:
        return "", after
    if line.endswith("."):
        return "", after
    # Mostly upper or Title Case -> looks like a heading title.
    letters = [c for c in line if c.isalpha()]
    if not letters:
        return "", after
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    if upper_ratio < 0.5 and not line[0].isupper():
        return "", after
    return line, nl


def _scan(text: str) -> list[_Hit]:
    hits: list[_Hit] = []
    # Track byte ranges consumed by next-line continuation titles so we
    # don't re-detect those title lines as separate headings.
    consumed_ranges: list[tuple[int, int]] = []
    for m in _BAB_RE.finditer(text):
        own_title = m["title"].strip()
        end_of_line = m.end()
        if not own_title:
            extra, end_of_line = _next_line_title(text, m.end())
            title = f"BAB {m['n']} {extra}".strip() if extra else f"BAB {m['n']}".strip()
            if extra:
                consumed_ranges.append((m.end(), end_of_line))
        else:
            title = f"BAB {m['n']} {own_title}".strip()
        hits.append(_Hit(m.start(), end_of_line, "bab", 1, title, m["n"]))
    for m in _BAGIAN_RE.finditer(text):
        own_title = m["title"].strip()
        end_of_line = m.end()
        if not own_title:
            extra, end_of_line = _next_line_title(text, m.end())
            title = f"Bagian {m['n']} {extra}".strip() if extra else f"Bagian {m['n']}".strip()
            if extra:
                consumed_ranges.append((m.end(), end_of_line))
        else:
            title = f"Bagian {m['n']} {own_title}".strip()
        hits.append(_Hit(m.start(), end_of_line, "bagian", 2, title, m["n"]))
    for m in _PARAGRAF_RE.finditer(text):
        hits.append(_Hit(m.start(), m.end(), "paragraf", 3, f"Paragraf {m['n']} {m['title']}".strip(), m["n"]))
    for m in _PASAL_RE.finditer(text):
        hits.append(_Hit(m.start(), m.end(), "pasal", 4, f"Pasal {m['n']}".strip(), m["n"]))
    for m in _SECTION_RE.finditer(text):
        n = m["n"]
        dot_count = n.count(".")
        title = f"Section {n} {m['title']}".strip()
        hits.append(_Hit(m.start(), m.end(), "section", 1 + dot_count, title, n))
    for m in _CLAUSE_RE.finditer(text):
        n = m["n"]
        dot_count = n.count(".")
        hits.append(_Hit(m.start(), m.end(), "clause", 1 + dot_count, f"{n} {m['title']}".strip(), n))
    for m in _SCHEDULE_RE.finditer(text):
        title = f"{m['n']} {m['id']} {m['title']}".strip()
        hits.append(_Hit(m.start(), m.end(), "schedule", 1, title, m["id"]))
    for m in _STANDALONE_DEFINITIONS_RE.finditer(text):
        # Drop matches that fall inside a continuation-title we already
        # ate as part of a BAB/Bagian heading (e.g. "Bagian Kesatu" on
        # one line then "Definisi" on the next — that 'Definisi' is the
        # title of Bagian Kesatu, not a new section).
        if any(r0 <= m.start() < r1 for r0, r1 in consumed_ranges):
            continue
        hits.append(_Hit(m.start(), m.end(), "definitions", 1, m["title"].strip(), "1"))

    # De-dup overlapping matches: a SECTION line shouldn't also be matched
    # as a CLAUSE. Sort by start, then keep the longest-prefix match at each
    # offset (a "1.2 Section title" line matches both clause and section;
    # take the more specific one — section beats raw clause).
    hits.sort(key=lambda h: (h.start, -h.level))
    dedup: list[_Hit] = []
    seen_starts: set[int] = set()
    for h in hits:
        if h.start in seen_starts:
            continue
        seen_starts.add(h.start)
        dedup.append(h)
    dedup.sort(key=lambda h: h.start)
    return dedup


def parse_structure(text: str) -> OutlineNode:
    """Parse `text` into an outline tree. Returns the synthetic root.

    Root is level 0 with kind='root' and no parent. The children of root
    are the top-level structural nodes encountered in document order.
    """
    root = OutlineNode(kind="root", ordinal=0, title=None, span_start=0, span_end=len(text), level=0)
    hits = _scan(text)
    if not hits:
        return root

    # Stack of (level, node). Pop while the top has level >= incoming level.
    stack: list[tuple[int, OutlineNode]] = [(0, root)]
    sibling_counter: dict[tuple[int, str], int] = {}

    for h in hits:
        while stack and stack[-1][0] >= h.level:
            stack.pop()
        parent = stack[-1][1] if stack else root
        key = (id(parent), h.kind)
        ordinal = sibling_counter.get(key, 0)
        sibling_counter[key] = ordinal + 1

        node = OutlineNode(
            kind=h.kind,
            ordinal=ordinal,
            title=h.title or None,
            span_start=h.end_of_heading_line,  # body starts after the heading line
            span_end=len(text),  # provisional; corrected below
            level=h.level,
            parent=parent,
        )
        parent.children.append(node)
        stack.append((h.level, node))

    # Fix up span_end: each node ends where the next sibling/uncle begins.
    flat = list(root.walk())
    for i, n in enumerate(flat):
        if n is root:
            continue
        # next node at same-or-shallower level marks the boundary
        boundary = len(text)
        for m in flat[i + 1 :]:
            if m.level <= n.level:
                boundary = m.span_start
                # walk back to where the heading line actually started
                for h in hits:
                    if h.end_of_heading_line == m.span_start:
                        boundary = h.start
                        break
                break
        n.span_end = boundary

    return root


def find_definitions_node(root: OutlineNode) -> OutlineNode | None:
    """Locate the Definitions / Ketentuan Umum subtree, if present.

    We check for either:
      - a `definitions` kind (standalone "Definitions" heading), or
      - any structural node whose title contains a definitions keyword
        (catches "BAB I KETENTUAN UMUM", "Section 1 Definitions", etc.).
    """
    for n in root.walk():
        if n.kind == "definitions":
            return n
        if n.title and _DEFINITIONS_TITLE_RE.search(n.title):
            return n
    return None
