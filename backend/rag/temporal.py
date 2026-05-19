"""Point-in-time resolver across amendment chains."""
from __future__ import annotations

from datetime import date

from sqlalchemy import text

from backend.db.session import session_scope


async def pasal_as_of(
    peraturan_jenis: str,
    peraturan_nomor: str | None,
    peraturan_tahun: int | None,
    pasal_nomor: str,
    ayat_nomor: str | None = None,
    huruf: str | None = None,
    as_of: date | None = None,
) -> dict | None:
    """Return the pasal row valid at `as_of` (handles amendments).

    If `ayat_nomor` (and optionally `huruf`) is given, the returned dict
    also includes the specific sub-fragment text.
    """
    as_of = as_of or date.today()
    sql = text(
        """
        SELECT pasal.id, pasal.nomor, pasal.teks,
               pasal.effective_from, pasal.effective_to,
               p.id AS peraturan_id, p.jenis, p.nomor AS p_nomor, p.tahun,
               p.judul AS p_judul
        FROM pasal
        JOIN peraturan p ON p.id = pasal.peraturan_id
        WHERE p.jenis = :jenis
          AND (CAST(:nomor AS text) IS NULL OR p.nomor = :nomor)
          AND (CAST(:tahun AS int)  IS NULL OR p.tahun = :tahun)
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

        result: dict = {
            "id": row.id,
            "nomor": row.nomor,
            "teks": row.teks,
            "effective_from": row.effective_from.isoformat() if row.effective_from else None,
            "effective_to": row.effective_to.isoformat() if row.effective_to else None,
            "peraturan": {
                "id": row.peraturan_id,
                "jenis": row.jenis,
                "nomor": row.p_nomor,
                "tahun": row.tahun,
                "judul": row.p_judul,
                "label": _label(row.jenis, row.p_nomor, row.tahun),
            },
        }

        # Pull all ayat (always — useful for the agent to see context)
        ayat_rows = (
            await s.execute(
                text(
                    "SELECT id, nomor, teks FROM ayat WHERE pasal_id = :pid ORDER BY id"
                ),
                {"pid": row.id},
            )
        ).all()
        result["ayat"] = [{"id": a.id, "nomor": a.nomor, "teks": a.teks} for a in ayat_rows]

        if ayat_nomor:
            target_ayat = next((a for a in ayat_rows if a.nomor == ayat_nomor), None)
            if target_ayat is None:
                return None
            result["selected_ayat"] = {"id": target_ayat.id, "nomor": target_ayat.nomor, "teks": target_ayat.teks}
            if huruf:
                hr = (
                    await s.execute(
                        text(
                            "SELECT id, huruf, teks FROM huruf WHERE ayat_id = :aid AND huruf = :h"
                        ),
                        {"aid": target_ayat.id, "h": huruf},
                    )
                ).first()
                if hr is None:
                    return None
                result["selected_huruf"] = {"id": hr.id, "huruf": hr.huruf, "teks": hr.teks}

    return result


def _label(jenis: str, nomor: str | None, tahun: int | None) -> str:
    if jenis in {"KUHP", "KUHPerdata", "KUHAP", "UUD"}:
        return jenis
    return f"{jenis} {nomor}/{tahun}" if nomor else jenis
