"""Backfill helper: populate Phase 8 metadata on rows that pre-date it.

For every existing Peraturan row:
  - Compute `hierarchy_level` from `jenis` via `legal.hierarchy.level_of`.
  - Run the promulgation parser over its `raw_text` (if present) to
    fill `ditetapkan_di`, `tanggal_diundangkan`, `lembaran_negara`,
    `tambahan_lembaran_negara`, `berita_negara`.

Idempotent — only writes columns that are currently NULL so a partial
backfill can resume without overwriting hand-curated values.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class BackfillStats:
    scanned: int = 0
    level_set: int = 0
    promul_fields_set: int = 0


async def backfill_hierarchy_and_promulgation(limit: int | None = None) -> BackfillStats:
    from sqlalchemy import select

    from backend.db import models
    from backend.db.session import session_scope
    from backend.legal.hierarchy import level_of
    from backend.legal.promulgation import parse_promulgation

    stats = BackfillStats()
    async with session_scope() as s:
        q = select(models.Peraturan).order_by(models.Peraturan.id)
        if limit is not None:
            q = q.limit(limit)
        rows = (await s.execute(q)).scalars().all()
        for per in rows:
            stats.scanned += 1
            jenis = per.jenis.value if hasattr(per.jenis, "value") else str(per.jenis)
            if per.hierarchy_level is None:
                per.hierarchy_level = level_of(jenis)
                stats.level_set += 1
            if per.raw_text:
                promul = parse_promulgation(per.raw_text)
                touched = False
                if per.ditetapkan_di is None and promul.ditetapkan_di:
                    per.ditetapkan_di = promul.ditetapkan_di
                    touched = True
                if per.tanggal_ditetapkan is None and promul.tanggal_ditetapkan:
                    per.tanggal_ditetapkan = promul.tanggal_ditetapkan
                    touched = True
                if per.tanggal_diundangkan is None and promul.tanggal_diundangkan:
                    per.tanggal_diundangkan = promul.tanggal_diundangkan
                    touched = True
                if per.lembaran_negara is None and promul.lembaran_negara:
                    per.lembaran_negara = promul.lembaran_negara
                    touched = True
                if (
                    per.tambahan_lembaran_negara is None
                    and promul.tambahan_lembaran_negara
                ):
                    per.tambahan_lembaran_negara = promul.tambahan_lembaran_negara
                    touched = True
                if per.berita_negara is None and promul.berita_negara:
                    per.berita_negara = promul.berita_negara
                    touched = True
                if touched:
                    stats.promul_fields_set += 1
    return stats
