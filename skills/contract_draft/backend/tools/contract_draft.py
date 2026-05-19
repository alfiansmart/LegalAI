"""Generate a draft perjanjian from a template + parameters + optional
standard clauses pulled from the clause_library skill."""
from __future__ import annotations

from typing import Any


async def execute(agent=None, args: dict | None = None) -> dict:
    from backend.documents import service, templates
    from backend.skills_loader import SkillRegistry
    from backend.config import get_settings

    args = args or {}
    template_id = args.get("template_id")
    if not template_id:
        return {"status": "error", "message": "missing template_id"}
    parties = args.get("parties") or []
    params: dict[str, Any] = dict(args.get("params") or {})
    include_clause_slugs: list[str] = list(args.get("include_clauses") or [])

    # Resolve standard clauses via clause_library skill (best-effort).
    resolved_clauses: list[dict] = []
    if include_clause_slugs:
        registry = SkillRegistry.from_dir(get_settings().skills_dir)
        try:
            cl = registry.get("clause_library")
            for slug in include_clause_slugs:
                res = await cl.call("clause_get", {"slug": slug})
                if res.get("status") == "ok":
                    resolved_clauses.append(res["clause"])
        except KeyError:
            pass

    # Render the template.
    try:
        content = templates.render(
            template_id,
            {"parties": parties, "include_clauses": resolved_clauses, **params},
        )
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:  # noqa: BLE001 — bubble Jinja errors as message
        return {"status": "error", "message": f"render failed: {type(e).__name__}: {e}"}

    # Persist as a draft document.
    title = params.get("title") or f"Draft {template_id}"
    kind = params.get("kind") or _kind_for_template(template_id)
    session_id = getattr(agent, "session_id", None)
    doc_id = await service.create_draft(
        user_id=session_id,
        title=title,
        kind=kind,
        content=content,
        template_id=template_id,
    )

    return {
        "status": "ok",
        "document_id": doc_id,
        "template_id": template_id,
        "kind": kind,
        "content_preview": content[:600],
        "clauses_included": [c.get("title") for c in resolved_clauses],
    }


def _kind_for_template(template_id: str) -> str:
    if template_id in {"somasi"}:
        return "somasi"
    if template_id in {"surat_kuasa"}:
        return "surat_kuasa"
    if template_id in {"legal_memo"}:
        return "memo"
    return "perjanjian"
