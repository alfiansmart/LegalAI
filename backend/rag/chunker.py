"""Structure-aware chunker for uploaded legal documents.

Key invariants:
  - A chunk is never split across the boundary of a Pasal or numbered
    clause. Splitting a defined obligation across two embeddings is
    exactly what we want to avoid.
  - Each chunk carries its `breadcrumb` (the heading path that contains
    it) and `parent_summary` (the title of the enclosing section), so a
    retrieved chunk arrives at the model with structural context.
  - Leaves that exceed `max_tokens` are subdivided at sentence
    boundaries with a small overlap. Sentence boundary detection is
    lightweight (no NLTK dependency).

Token counting is approximate — we use a simple `len(text) // 4` heuristic
which is good enough for chunk sizing. Real token accounting happens at
the model boundary, not here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from backend.rag.doc_structure import OutlineNode, parse_structure

DEFAULT_MAX_TOKENS = 800
DEFAULT_OVERLAP_TOKENS = 100


@dataclass(slots=True)
class Chunk:
    ordinal: int
    text: str
    breadcrumb: str
    parent_summary: str
    outline_path: list[OutlineNode]  # leaf-to-root not included; root-to-leaf
    token_count: int

    @property
    def leaf(self) -> OutlineNode | None:
        return self.outline_path[-1] if self.outline_path else None


def _est_tokens(text: str) -> int:
    return max(1, len(text) // 4)


_SENT_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z“\"(])|\n{2,}")


def _split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENT_BOUNDARY.split(text) if p and p.strip()]
    return parts or [text.strip()]


def _windows(sentences: list[str], max_tokens: int, overlap_tokens: int) -> list[str]:
    """Pack sentences into windows of ≤ max_tokens with overlap."""
    out: list[str] = []
    cur: list[str] = []
    cur_tokens = 0
    for s in sentences:
        st = _est_tokens(s)
        if cur and cur_tokens + st > max_tokens:
            out.append(" ".join(cur).strip())
            # build overlap: keep trailing sentences whose total ≤ overlap_tokens
            keep: list[str] = []
            keep_tokens = 0
            for ks in reversed(cur):
                kst = _est_tokens(ks)
                if keep_tokens + kst > overlap_tokens:
                    break
                keep.insert(0, ks)
                keep_tokens += kst
            cur = keep
            cur_tokens = keep_tokens
        cur.append(s)
        cur_tokens += st
    if cur:
        out.append(" ".join(cur).strip())
    return [w for w in out if w]


def _leaves(node: OutlineNode) -> list[OutlineNode]:
    """Return outline nodes whose body text we should chunk.

    A node is a "leaf for chunking" if it has no children, OR if its
    own pre-children body is non-trivial (e.g. a Pasal that contains
    Ayat children also has a header sentence above them).
    """
    leaves: list[OutlineNode] = []
    for n in node.walk():
        if n.kind == "root":
            continue
        if not n.children:
            leaves.append(n)
    return leaves


def _body_text(text: str, node: OutlineNode) -> str:
    """Extract the text belonging to this node, excluding child nodes."""
    if not node.children:
        return text[node.span_start : node.span_end].strip()
    # Take only the text up to the first child heading.
    end = min(c.span_start for c in node.children)
    return text[node.span_start : end].strip()


def _path_to(node: OutlineNode) -> list[OutlineNode]:
    out: list[OutlineNode] = []
    n: OutlineNode | None = node
    while n and n.kind != "root":
        out.append(n)
        n = n.parent
    return list(reversed(out))


def chunk_document(
    text: str,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> tuple[OutlineNode, list[Chunk]]:
    """Parse + chunk in one call. Returns (outline_root, chunks)."""
    root = parse_structure(text)
    chunks: list[Chunk] = []
    ordinal = 0

    if not root.children:
        # No headings at all — fall back to plain sentence-window chunking.
        for window in _windows(_split_sentences(text), max_tokens, overlap_tokens):
            chunks.append(
                Chunk(
                    ordinal=ordinal,
                    text=window,
                    breadcrumb="",
                    parent_summary="",
                    outline_path=[],
                    token_count=_est_tokens(window),
                )
            )
            ordinal += 1
        return root, chunks

    for leaf in _leaves(root):
        body = _body_text(text, leaf)
        if not body:
            continue
        path = _path_to(leaf)
        breadcrumb = " / ".join((n.title or n.kind.title()) for n in path)
        # parent_summary: titles of all ancestors (exclude self)
        parent_summary = " > ".join((n.title or n.kind.title()) for n in path[:-1]) or breadcrumb

        if _est_tokens(body) <= max_tokens:
            chunks.append(
                Chunk(
                    ordinal=ordinal,
                    text=body,
                    breadcrumb=breadcrumb,
                    parent_summary=parent_summary,
                    outline_path=path,
                    token_count=_est_tokens(body),
                )
            )
            ordinal += 1
            continue

        for window in _windows(_split_sentences(body), max_tokens, overlap_tokens):
            chunks.append(
                Chunk(
                    ordinal=ordinal,
                    text=window,
                    breadcrumb=breadcrumb,
                    parent_summary=parent_summary,
                    outline_path=path,
                    token_count=_est_tokens(window),
                )
            )
            ordinal += 1

    return root, chunks
