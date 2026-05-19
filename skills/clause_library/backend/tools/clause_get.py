"""Return a standard clause. Phase-0: in-memory dictionary."""
from __future__ import annotations

_CLAUSES = {
    "force_majeure": {
        "title": "Keadaan Kahar (Force Majeure)",
        "text": (
            "Para Pihak dibebaskan dari tanggung jawab atas keterlambatan atau "
            "kegagalan pelaksanaan kewajiban berdasarkan Perjanjian ini sepanjang "
            "disebabkan oleh keadaan kahar (force majeure), termasuk namun tidak "
            "terbatas pada bencana alam, perang, huru-hara, pemogokan umum, "
            "wabah/pandemi, atau peraturan Pemerintah yang melarang pelaksanaan "
            "kewajiban. Pihak yang terdampak wajib memberitahukan secara tertulis "
            "kepada Pihak lainnya dalam waktu 7 (tujuh) hari kalender sejak "
            "terjadinya keadaan kahar tersebut."
        ),
        "dasar_hukum": ["Pasal 1244 KUHPerdata", "Pasal 1245 KUHPerdata"],
    },
    "arbitrase_bani": {
        "title": "Penyelesaian Sengketa Melalui BANI",
        "text": (
            "Setiap perselisihan yang timbul dari atau berkaitan dengan Perjanjian "
            "ini, yang tidak dapat diselesaikan secara musyawarah dalam waktu 30 "
            "(tiga puluh) hari kalender, akan diselesaikan melalui Badan Arbitrase "
            "Nasional Indonesia (BANI) sesuai dengan Peraturan dan Prosedur BANI "
            "yang berlaku. Putusan arbitrase bersifat final dan mengikat."
        ),
        "dasar_hukum": ["UU 30/1999"],
    },
    "choice_of_law": {
        "title": "Hukum yang Berlaku",
        "text": "Perjanjian ini diatur oleh dan ditafsirkan berdasarkan hukum Negara Republik Indonesia.",
        "dasar_hukum": [],
    },
}


def execute(agent=None, args: dict | None = None) -> dict:
    args = args or {}
    slug = args.get("slug", "")
    if slug not in _CLAUSES:
        return {"status": "not_found", "available": list(_CLAUSES.keys())}
    return {"status": "ok", "clause": _CLAUSES[slug]}
