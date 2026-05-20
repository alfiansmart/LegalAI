"""Visual artifacts that skills can emit alongside text.

A skill returning `{"status": "ok", "summary": "...", "artifacts": [...]}`
gets its artifacts collected by the harness and shipped to the client
alongside the textual reply. The frontend's ArtifactRenderer dispatches
on `type` and renders mermaid diagrams, data tables, charts, timelines,
trees, heatmaps, diffs, and graphs.

The protocol is intentionally thin: each artifact is `{id, type, title,
data, caption?}` with the `data` shape varying per type. We don't lock
down the data schemas in Pydantic — the frontend is permissive and the
skill author who knows what they're rendering. This avoids two layers
of duplicate validation while staying inspectable.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal


ArtifactType = Literal[
    "mermaid",
    "table",
    "chart",
    "timeline",
    "tree",
    "heatmap",
    "diff",
    "graph",
]

_VALID_TYPES = {"mermaid", "table", "chart", "timeline", "tree", "heatmap", "diff", "graph"}


@dataclass(slots=True)
class Artifact:
    type: str
    title: str
    data: dict[str, Any]
    caption: str | None = None
    id: str = field(default_factory=lambda: "art_" + uuid.uuid4().hex[:12])

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"id": self.id, "type": self.type, "title": self.title, "data": self.data}
        if self.caption:
            out["caption"] = self.caption
        return out


class ArtifactCollector:
    """Threaded through the harness; skills append to it.

    Order is preserved. Duplicate IDs are tolerated (the frontend uses
    them as React keys, but we don't rely on cross-skill uniqueness).
    """

    def __init__(self) -> None:
        self._items: list[Artifact] = []

    def emit(
        self,
        type: str,
        title: str,
        data: dict[str, Any],
        *,
        caption: str | None = None,
    ) -> Artifact:
        if type not in _VALID_TYPES:
            raise ValueError(f"unknown artifact type {type!r} (expected one of {sorted(_VALID_TYPES)})")
        a = Artifact(type=type, title=title, data=data, caption=caption)
        self._items.append(a)
        return a

    def extend(self, items: list[Artifact | dict]) -> None:
        for it in items:
            if isinstance(it, Artifact):
                self._items.append(it)
            elif isinstance(it, dict) and it.get("type") in _VALID_TYPES:
                self._items.append(
                    Artifact(
                        type=it["type"],
                        title=it.get("title", ""),
                        data=it.get("data", {}),
                        caption=it.get("caption"),
                        id=it.get("id") or "art_" + uuid.uuid4().hex[:12],
                    )
                )

    def items(self) -> list[Artifact]:
        return list(self._items)

    def to_list(self) -> list[dict[str, Any]]:
        return [a.to_dict() for a in self._items]

    def __len__(self) -> int:
        return len(self._items)


# ---------------------------------------------------------------------------
# Convenience builders — skills call these to keep their handlers terse.
# Each builder returns a dict ready to drop into a skill's return value
# under the key "artifacts": [...].
# ---------------------------------------------------------------------------


def mermaid(title: str, source: str, *, caption: str | None = None) -> dict[str, Any]:
    return {"type": "mermaid", "title": title, "data": {"source": source}, **({"caption": caption} if caption else {})}


def table(
    title: str,
    columns: list[str],
    rows: list[list[Any]],
    *,
    caption: str | None = None,
) -> dict[str, Any]:
    return {
        "type": "table",
        "title": title,
        "data": {"columns": columns, "rows": rows},
        **({"caption": caption} if caption else {}),
    }


def chart(
    title: str,
    kind: str,
    series: list[dict],
    *,
    caption: str | None = None,
) -> dict[str, Any]:
    """`kind` ∈ {bar, line, pie}. `series` is renderer-specific (Recharts shape)."""
    return {
        "type": "chart",
        "title": title,
        "data": {"kind": kind, "series": series},
        **({"caption": caption} if caption else {}),
    }


def timeline(
    title: str,
    events: list[dict],
    *,
    caption: str | None = None,
) -> dict[str, Any]:
    """Each event: {date|year, label, detail?, kind?}."""
    return {
        "type": "timeline",
        "title": title,
        "data": {"events": events},
        **({"caption": caption} if caption else {}),
    }


def tree(title: str, root: dict, *, caption: str | None = None) -> dict[str, Any]:
    """`root` is a node {label, children?: [..], detail?}."""
    return {
        "type": "tree",
        "title": title,
        "data": {"root": root},
        **({"caption": caption} if caption else {}),
    }


def heatmap(
    title: str,
    rows: list[str],
    cols: list[str],
    cells: list[list[dict | int | float | str | None]],
    *,
    caption: str | None = None,
) -> dict[str, Any]:
    return {
        "type": "heatmap",
        "title": title,
        "data": {"rows": rows, "cols": cols, "cells": cells},
        **({"caption": caption} if caption else {}),
    }


def diff(
    title: str,
    base_text: str,
    head_text: str,
    *,
    annotations: list[dict] | None = None,
    caption: str | None = None,
) -> dict[str, Any]:
    """`annotations` overlay AI commentary on hunks: [{line, message, severity?}]."""
    return {
        "type": "diff",
        "title": title,
        "data": {"base": base_text, "head": head_text, "annotations": annotations or []},
        **({"caption": caption} if caption else {}),
    }


def graph(
    title: str,
    nodes: list[dict],
    edges: list[dict],
    *,
    caption: str | None = None,
) -> dict[str, Any]:
    """`nodes`: [{id, label, kind?}], `edges`: [{src, dst, kind?, label?}]."""
    return {
        "type": "graph",
        "title": title,
        "data": {"nodes": nodes, "edges": edges},
        **({"caption": caption} if caption else {}),
    }
