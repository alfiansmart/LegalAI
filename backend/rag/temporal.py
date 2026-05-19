"""Point-in-time resolver across amendment chains."""
from __future__ import annotations

from datetime import date

from sqlalchemy import text

from backend.db.session import session_scope


async def pasal_as_of(peraturan_jenis: str, peraturan_nomor: str, peraturan_tahun: int,
                     pasal_nomor: str, as_of: date) -> dict | None:
    """Return the pasal row valid at `as_of` (handles amendments)."""
    sql = text(
        """
        SELECT pasal.id, pasal.nomor, pasal.teks,
               pasal.effective_from, pasal.effective_to
        FROM pasal
        JOIN peraturan p ON p.id = pasal.peraturan_id
        WHERE p.jenis = :jenis
          AND (p.nomor = :nomor OR p.nomor IS NULL)
          AND (p.tahun = :tahun OR p.tahun IS NULL)
          AND pasal.nomor = :pasal_nomor
          AND (pasal.effective_from IS NULL OR pasal.effective_from <= :as_of)
          AND (pasal.effective_to   IS NULL OR pasal.effective_to   >= :as_of)
        ORDER BY pasal.effective_from DESC NULLS LAST
        LIMIT 1
        """
    )
    async with session_scope() as s:
        row = (
            await s.execute(
                sql,
                {
                    "jenis": peraturan_jenis,
                    "nomor": peraturan_nomor,
                    "tahun": peraturan_tahun,
                    "pasal_nomor": pasal_nomor,
                    "as_of": as_of,
                },
            )
        ).first()
    if not row:
        return None
    return {
        "id": row.id,
        "nomor": row.nomor,
        "teks": row.teks,
        "effective_from": row.effective_from.isoformat() if row.effective_from else None,
        "effective_to": row.effective_to.isoformat() if row.effective_to else None,
    }
