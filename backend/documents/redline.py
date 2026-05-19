"""Redline diff between two document texts."""
from __future__ import annotations

import difflib
from dataclasses import dataclass


@dataclass(slots=True)
class Hunk:
    kind: str  # "equal" | "insert" | "delete" | "replace"
    base: str
    head: str


def diff(base: str, head: str) -> list[Hunk]:
    sm = difflib.SequenceMatcher(a=base.splitlines(keepends=True), b=head.splitlines(keepends=True))
    out: list[Hunk] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        out.append(
            Hunk(
                kind=tag,
                base="".join(sm.a[i1:i2]),
                head="".join(sm.b[j1:j2]),
            )
        )
    return out


def unified(base: str, head: str, base_label: str = "baseline", head_label: str = "draft") -> str:
    return "".join(
        difflib.unified_diff(
            base.splitlines(keepends=True),
            head.splitlines(keepends=True),
            fromfile=base_label,
            tofile=head_label,
            n=3,
        )
    )
