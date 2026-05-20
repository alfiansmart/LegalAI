"""Task-button endpoints — the primary UI surface.

Each task is a deterministic button → endpoint → skill → structured panel.
No LLM-driven routing here: the user has already told us which task they
want by clicking the button. The endpoints are thin wrappers that call
the appropriate skill or pipeline directly, then return structured JSON
plus visual artifacts.

This file is the heart of Phase 4.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from backend.documents import service as doc_service, upload_pipeline
from backend.skills_loader import SkillRegistry
from backend.config import get_settings

router = APIRouter()

_settings = get_settings()
# Single registry instance, loaded once. Skills don't change at runtime.
_registry = SkillRegistry.from_dir(_settings.skills_dir)


def _call_skill_tool(tool_name: str, args: dict) -> Any:
    """Direct skill invocation, no LLM loop, no harness — task endpoints
    use this for button-driven tasks where the user has already picked
    the action."""
    skill = _registry.find_by_tool(tool_name)
    if skill is None:
        raise HTTPException(500, f"skill for tool {tool_name!r} not found")
    return skill.call(tool_name, args, agent=None)


# ---------------------------------------------------------------------------
# 📤 Upload — extract, structure-aware chunking, contextualise + embed,
#              defined-terms, peraturan citation backfill.
# ---------------------------------------------------------------------------


@router.post("/upload-and-index")
async def upload_and_index(
    file: UploadFile = File(...),
    matter_id: int | None = Form(default=None),
    title: str | None = Form(default=None),
) -> dict:
    data = await file.read()
    if not data:
        raise HTTPException(400, "empty file")
    try:
        result = await upload_pipeline.ingest_uploaded_document(
            filename=file.filename or "uploaded",
            data=data,
            matter_id=matter_id,
            title=title,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {
        "document_id": result.document_id,
        "filename": file.filename,
        "bytes": len(data),
        "text_chars": result.text_chars,
        "chunks_inserted": result.chunks_inserted,
        "outline_nodes": result.outline_nodes,
        "terms_extracted": result.terms_extracted,
        "citations_inferred": result.citations_inferred,
    }


# ---------------------------------------------------------------------------
# ✍️ Draft
# ---------------------------------------------------------------------------


class DraftReq(BaseModel):
    template_id: str
    parties: list[str] = []
    params: dict[str, Any] = {}
    include_clauses: list[str] = []
    matter_id: int | None = None
    title: str | None = None


@router.post("/draft")
async def draft(req: DraftReq) -> dict:
    args = {
        "template_id": req.template_id,
        "parties": req.parties,
        "params": req.params,
        "include_clauses": req.include_clauses,
        "matter_id": req.matter_id,
        "title": req.title,
    }
    return await _call_skill_tool("contract_draft", args)


# ---------------------------------------------------------------------------
# 🔍 Review
# ---------------------------------------------------------------------------


class ReviewReq(BaseModel):
    document_id: int
    compliance_against: list[str] = []


@router.post("/review")
async def review(req: ReviewReq) -> dict:
    return await _call_skill_tool(
        "contract_review",
        {"document_id": req.document_id, "compliance_against": req.compliance_against},
    )


# ---------------------------------------------------------------------------
# ⚖️ Compare
# ---------------------------------------------------------------------------


class CompareReq(BaseModel):
    head_document_id: int
    base_document_id: int | None = None
    base_template_id: str | None = None


@router.post("/compare")
async def compare(req: CompareReq) -> dict:
    if not req.base_document_id and not req.base_template_id:
        raise HTTPException(400, "need base_document_id or base_template_id")
    return await _call_skill_tool(
        "compare_with_commentary",
        {
            "head_document_id": req.head_document_id,
            "base_document_id": req.base_document_id,
            "base_template_id": req.base_template_id,
        },
    )


# ---------------------------------------------------------------------------
# 📚 Research — multi-skill chain: peraturan_search → citation_trace →
#               legal_memo_compose. Each leg is invoked directly so the
#               endpoint stays deterministic.
# ---------------------------------------------------------------------------


class ResearchReq(BaseModel):
    issue: str
    as_of: str | None = None
    save_as_memo: bool = False
    matter_id: int | None = None


@router.post("/research")
async def research(req: ResearchReq) -> dict:
    hits_result = await _call_skill_tool(
        "peraturan_search",
        {"q": req.issue, "as_of": req.as_of, "k": 10},
    )

    memo_result: dict[str, Any] = {}
    memo_doc_id: int | None = None
    if req.save_as_memo:
        memo_result = await _call_skill_tool(
            "legal_memo_compose",
            {
                "issue": req.issue,
                "facts": req.issue,  # use the issue text as facts when called from the button
                "evidence": hits_result.get("hits") if isinstance(hits_result, dict) else [],
            },
        )
        memo_text = memo_result.get("memo") if isinstance(memo_result, dict) else None
        if memo_text:
            memo_doc_id = await doc_service.create_draft(
                user_id=None,
                title=f"Memo: {req.issue[:80]}",
                kind="memo",
                content=memo_text,
                matter_id=req.matter_id,
            )

    artifacts: list[dict] = []
    if isinstance(hits_result, dict):
        artifacts.extend(hits_result.get("artifacts") or [])
    if isinstance(memo_result, dict):
        artifacts.extend(memo_result.get("artifacts") or [])

    return {
        "status": "ok",
        "hits": hits_result.get("hits") if isinstance(hits_result, dict) else [],
        "memo_preview": memo_result.get("memo") if isinstance(memo_result, dict) else None,
        "memo_document_id": memo_doc_id,
        "artifacts": artifacts,
    }


# ---------------------------------------------------------------------------
# 📝 Summarize
# ---------------------------------------------------------------------------


class SummarizeReq(BaseModel):
    document_id: int


@router.post("/summarize")
async def summarize(req: SummarizeReq) -> dict:
    return await _call_skill_tool("document_summarize", {"document_id": req.document_id})


# ---------------------------------------------------------------------------
# 🧾 Extract
# ---------------------------------------------------------------------------


class ExtractReq(BaseModel):
    document_id: int


@router.post("/extract-facts")
async def extract_facts(req: ExtractReq) -> dict:
    return await _call_skill_tool("document_extract", {"document_id": req.document_id})
