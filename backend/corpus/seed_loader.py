"""Load seed JSON (KUHP / KUHPerdata / KUHAP / UUD 1945) into the DB.

Run with:
    docker compose exec backend python -m backend.corpus.seed_loader
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from backend.db import models
from backend.db.session import session_scope

SEED_DIR = Path("seed")


async def load_one(path: Path) -> None:
    data = json.loads(path.read_text())
    jenis = models.JenisPeraturan(data["jenis"])

    async with session_scope() as s:
        existing = (
            await s.execute(
                select(models.Peraturan).where(
                    models.Peraturan.jenis == jenis,
                    models.Peraturan.nomor == data.get("nomor"),
                    models.Peraturan.tahun == data.get("tahun"),
                )
            )
        ).scalar_one_or_none()
        if existing:
            print(f"[seed] skip (already loaded): {path.name}")
            return

        per = models.Peraturan(
            jenis=jenis,
            nomor=data.get("nomor"),
            tahun=data.get("tahun"),
            judul=data["judul"],
            tentang=data.get("tentang"),
            status=models.StatusPeraturan(data.get("status", "berlaku")),
            penerbit=data.get("penerbit"),
            source_url=data.get("source_url"),
        )
        s.add(per)
        await s.flush()

        for p in data.get("pasal", []):
            pasal = models.Pasal(
                peraturan_id=per.id,
                nomor=p["nomor"],
                teks=p.get("teks", ""),
            )
            s.add(pasal)
            await s.flush()
            for a in p.get("ayat", []):
                ayat = models.Ayat(pasal_id=pasal.id, nomor=a["nomor"], teks=a.get("teks", ""))
                s.add(ayat)
                await s.flush()
                for h in a.get("huruf", []):
                    s.add(models.Huruf(ayat_id=ayat.id, huruf=h["huruf"], teks=h.get("teks", "")))
        print(f"[seed] loaded: {path.name} ({len(data.get('pasal', []))} pasal)")


async def main() -> None:
    files = sorted(SEED_DIR.glob("*.json"))
    if not files:
        print(f"[seed] no JSON files in {SEED_DIR}/")
        return
    for f in files:
        await load_one(f)


if __name__ == "__main__":
    asyncio.run(main())
