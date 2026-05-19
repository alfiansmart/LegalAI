"""Generate a draft perjanjian. Phase-1 implementation will render from
.docx / .md templates with Jinja2 substitution + LLM-fill for narrative
clauses, then persist via documents.service.create_draft.
"""
from __future__ import annotations


def execute(agent=None, args: dict | None = None) -> dict:
    args = args or {}
    return {
        "status": "not_implemented",
        "message": "contract_draft implementation lands in Phase 2.",
        "received": args,
    }
