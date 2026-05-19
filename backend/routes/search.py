from fastapi import APIRouter
from pydantic import BaseModel

from backend.rag.retriever import HybridRetriever

router = APIRouter()


class SearchRequest(BaseModel):
    q: str
    k: int = 10
    jenis: list[str] | None = None
    as_of: str | None = None
    expand_graph: bool = True


class SearchHit(BaseModel):
    pasal_id: int
    peraturan: str
    pasal: str
    ayat: str | None = None
    huruf: str | None = None
    score: float
    snippet: str


class SearchResponse(BaseModel):
    hits: list[SearchHit]


@router.post("", response_model=SearchResponse)
async def search(req: SearchRequest) -> SearchResponse:
    retriever = HybridRetriever()
    hits = await retriever.search(
        q=req.q, k=req.k, jenis=req.jenis, as_of=req.as_of, expand_graph=req.expand_graph
    )
    return SearchResponse(hits=[SearchHit(**h) for h in hits])
