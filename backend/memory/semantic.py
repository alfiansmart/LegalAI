"""Semantic memory — long-term user facts (Mem0-style).

Stored in UserMemory with embedding for recall. Exposed to the agent
as tools `memory.recall`, `memory.add`, `memory.forget`.
"""
from __future__ import annotations

from sqlalchemy import text

from backend.db.session import session_scope


async def add(user_id: str, content: str, kind: str = "fact") -> int:
    from backend.rag.embeddings import embed_one

    vec = embed_one(content)
    sql = text(
        """
        INSERT INTO user_memory (user_id, kind, content, embedding)
        VALUES (:user_id, :kind, :content, CAST(:vec AS vector))
        RETURNING id
        """
    )
    async with session_scope() as s:
        row = (await s.execute(sql, {"user_id": user_id, "kind": kind, "content": content, "vec": vec})).first()
    return row.id


async def recall(user_id: str, query: str, k: int = 5) -> list[dict]:
    from backend.rag.embeddings import embed_one

    qvec = embed_one(query, is_query=True)
    sql = text(
        """
        SELECT id, content, kind,
               1 - (embedding <=> CAST(:qvec AS vector)) AS score
        FROM user_memory
        WHERE user_id = :user_id AND embedding IS NOT NULL
        ORDER BY embedding <=> CAST(:qvec AS vector)
        LIMIT :k
        """
    )
    async with session_scope() as s:
        rows = (await s.execute(sql, {"user_id": user_id, "qvec": qvec, "k": k})).all()
    return [{"id": r.id, "content": r.content, "kind": r.kind, "score": float(r.score)} for r in rows]


async def forget(memory_id: int) -> None:
    sql = text("DELETE FROM user_memory WHERE id = :id")
    async with session_scope() as s:
        await s.execute(sql, {"id": memory_id})
