"""Cache-Augmented Generation (CAG) — the long-context fallback path.

For documents that fit in Claude's context window we skip RAG entirely:
load the full document text into the prompt, mark it as a cached prefix,
and let the model attend to the whole thing directly. After the first
call the document costs ~10% of normal input pricing on cache hit.

The decision boundary is a simple token budget. Below it we use CAG;
above it we fall back to chunked retrieval. The threshold is generous
(150K tokens default — Opus 4.7 handles 200K comfortably with room for
the query, conversation history, and reply).
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.config import get_settings
from backend.db import models
from backend.db.session import session_scope

_settings = get_settings()

# Rough char-per-token heuristic for sizing decisions only.
_CHARS_PER_TOKEN = 4
# Reserve some of the model's window for conversation + system + reply.
DEFAULT_CAG_BUDGET_TOKENS = 150_000


@dataclass(slots=True)
class CAGPayload:
    """A bundle of full-document texts that should be loaded into the prompt."""

    items: list[dict]  # [{document_id, title, text}]
    total_tokens: int

    def as_anthropic_blocks(self) -> list[dict]:
        """Return text blocks suitable for inclusion in a `messages` content array.

        Each item is its own block with `cache_control: ephemeral`, so the
        large document payloads get cached on the Anthropic side and we
        pay full price only on the first call within a session.
        """
        out: list[dict] = []
        for it in self.items:
            out.append(
                {
                    "type": "text",
                    "text": f"<dokumen id={it['document_id']} title=\"{it['title']}\">\n"
                    f"{it['text']}\n</dokumen>",
                    "cache_control": {"type": "ephemeral"},
                }
            )
        return out


def _estimate_tokens(s: str) -> int:
    return max(1, len(s) // _CHARS_PER_TOKEN)


async def cag_payload_for_matter(
    matter_id: int,
    *,
    budget_tokens: int = DEFAULT_CAG_BUDGET_TOKENS,
) -> CAGPayload | None:
    """Build a CAG payload of *all* documents in a matter, if they fit.

    Returns None when the matter's documents wouldn't fit in the budget;
    callers should then fall back to chunked retrieval.
    """
    from sqlalchemy import select

    async with session_scope() as s:
        rows = (
            (
                await s.execute(
                    select(models.Document).where(models.Document.matter_id == matter_id)
                )
            )
            .scalars()
            .all()
        )
        items: list[dict] = []
        total = 0
        for d in rows:
            versions = (
                (
                    await s.execute(
                        select(models.DocumentVersion)
                        .where(models.DocumentVersion.document_id == d.id)
                        .order_by(models.DocumentVersion.version.desc())
                    )
                )
                .scalars()
                .all()
            )
            content = versions[0].content if versions else ""
            if not content:
                continue
            t = _estimate_tokens(content)
            if total + t > budget_tokens:
                return None
            total += t
            items.append({"document_id": d.id, "title": d.title, "text": content})
    if not items:
        return None
    return CAGPayload(items=items, total_tokens=total)


async def cag_payload_for_document(
    document_id: int,
    *,
    budget_tokens: int = DEFAULT_CAG_BUDGET_TOKENS,
) -> CAGPayload | None:
    """Build a CAG payload for a single document, if it fits the budget."""
    from sqlalchemy import select

    async with session_scope() as s:
        d = await s.get(models.Document, document_id)
        if not d:
            return None
        versions = (
            (
                await s.execute(
                    select(models.DocumentVersion)
                    .where(models.DocumentVersion.document_id == document_id)
                    .order_by(models.DocumentVersion.version.desc())
                )
            )
            .scalars()
            .all()
        )
        content = versions[0].content if versions else ""
        if not content:
            return None
        t = _estimate_tokens(content)
        if t > budget_tokens:
            return None
    return CAGPayload(
        items=[{"document_id": d.id, "title": d.title, "text": content}], total_tokens=t
    )
