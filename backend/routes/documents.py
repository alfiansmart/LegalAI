from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from backend.documents import export, redline, service, templates

router = APIRouter()


@router.get("")
async def list_documents(user_id: str | None = None) -> list[dict]:
    return await service.list_documents(user_id=user_id)


@router.get("/templates")
def list_templates() -> list[dict]:
    return [
        {"id": t.id, "title": t.title, "description": t.description}
        for t in templates.list_templates()
    ]


@router.get("/{doc_id}")
async def get_document(doc_id: int) -> dict:
    doc = await service.get_document(doc_id)
    if not doc:
        raise HTTPException(404, "document not found")
    return doc


class NewVersionReq(BaseModel):
    content: str
    note: str | None = None


@router.post("/{doc_id}/versions")
async def add_version(doc_id: int, req: NewVersionReq) -> dict:
    v = await service.new_version(doc_id, req.content, note=req.note)
    return {"document_id": doc_id, "version": v}


@router.get("/{doc_id}/export")
async def export_document(doc_id: int, format: str = "docx") -> Response:
    doc = await service.get_document(doc_id)
    if not doc:
        raise HTTPException(404, "document not found")
    content = doc["versions"][-1]["content"] if doc["versions"] else ""
    fmt = format.lower()
    if fmt == "md":
        return Response(
            content=export.to_markdown_bytes(content),
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="doc-{doc_id}.md"'},
        )
    if fmt in {"docx", "pdf"}:
        # Phase 2: pdf is approximated by docx; real PDF export comes later.
        data = export.to_docx_bytes(content, title=doc["title"])
        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="doc-{doc_id}.docx"'},
        )
    raise HTTPException(400, f"unsupported format: {format}")


class RedlineReq(BaseModel):
    base: str
    head: str


@router.post("/redline")
def redline_diff(req: RedlineReq) -> dict:
    return {
        "unified": redline.unified(req.base, req.head),
        "hunks": [
            {"kind": h.kind, "base": h.base, "head": h.head}
            for h in redline.diff(req.base, req.head)
        ],
    }
