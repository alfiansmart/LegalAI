from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class DocumentDraft(BaseModel):
    id: int
    title: str
    kind: str
    content: str
    version: int


@router.get("")
def list_documents() -> list[DocumentDraft]:
    return []


@router.get("/{doc_id}")
def get_document(doc_id: int) -> DocumentDraft:
    return DocumentDraft(id=doc_id, title="", kind="perjanjian", content="", version=1)
