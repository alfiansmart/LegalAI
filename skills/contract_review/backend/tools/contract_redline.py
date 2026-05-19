"""Diff a draft document against a baseline template."""
from __future__ import annotations


async def execute(agent=None, args: dict | None = None) -> dict:
    from backend.documents import redline, service, templates

    args = args or {}
    document_id = args.get("document_id")
    baseline_template_id = args.get("baseline_template_id")
    if not document_id or not baseline_template_id:
        return {"status": "error", "message": "need document_id and baseline_template_id"}

    head = await service.latest_content(int(document_id))
    if not head:
        return {"status": "error", "message": "document not found"}

    try:
        base = templates.render(baseline_template_id, args.get("baseline_params") or {})
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "message": f"baseline render failed: {e}"}

    hunks = redline.diff(base, head)
    unified = redline.unified(base, head)
    summary = {
        "added_lines": sum(1 for h in hunks if h.kind in {"insert", "replace"}),
        "removed_lines": sum(1 for h in hunks if h.kind in {"delete", "replace"}),
        "equal_blocks": sum(1 for h in hunks if h.kind == "equal"),
    }
    return {
        "status": "ok",
        "summary": summary,
        "unified": unified,
        "hunks": [{"kind": h.kind, "base": h.base[:400], "head": h.head[:400]} for h in hunks],
    }
