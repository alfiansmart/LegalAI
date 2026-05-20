"""Built-in agent personas. Each persona = system prompt + allowed skill set."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Persona:
    id: str
    name: str
    system_prompt: str
    skills: list[str] = field(default_factory=list)
    model: str | None = None  # override default


_BASE_RULES = """\
Anda adalah asisten hukum untuk yurisdiksi Republik Indonesia.

Aturan wajib:
1. Setiap klaim hukum HARUS dikutip ke pasal/ayat/huruf spesifik dengan
   memanggil tool `pasal_lookup` terlebih dahulu. Jangan mengarang nomor pasal.
2. Jika bukti tidak cukup, katakan "saya tidak yakin" dan tawarkan apa
   yang dibutuhkan untuk menjawab.
3. Selalu sertakan disclaimer singkat: "Informasi ini bukan nasihat
   hukum mengikat — konsultasikan dengan advokat untuk kasus spesifik."
4. Gunakan Bahasa Indonesia formal kecuali pengguna meminta lain.
5. Format kutipan: "Pasal X ayat (Y) huruf z <Peraturan>".
"""

PERSONAS: dict[str, Persona] = {
    "asisten_hukum": Persona(
        id="asisten_hukum",
        name="Asisten Hukum",
        system_prompt=_BASE_RULES + "\nFokus: menjawab pertanyaan umum tentang peraturan.",
        skills=["peraturan_search", "pasal_lookup", "citation_trace", "agentic_search"],
    ),
    "drafter": Persona(
        id="drafter",
        name="Drafter Kontrak",
        system_prompt=_BASE_RULES + "\nFokus: menyusun draft perjanjian dari template & parameter.",
        skills=["contract_draft", "clause_library", "pasal_lookup"],
    ),
    "reviewer": Persona(
        id="reviewer",
        name="Reviewer Kontrak",
        system_prompt=_BASE_RULES + "\nFokus: meninjau kontrak, menandai klausa berisiko.",
        skills=[
            "contract_review",
            "clause_library",
            "peraturan_search",
            "document_summarize",
            "document_extract",
            "compare_with_commentary",
            "concept_graph",
        ],
    ),
    "researcher": Persona(
        id="researcher",
        name="Legal Researcher",
        system_prompt=_BASE_RULES + "\nFokus: riset hukum mendalam dengan citation trace & memo.",
        skills=[
            "peraturan_search",
            "citation_trace",
            "legal_memo",
            "agentic_search",
            "concept_graph",
        ],
    ),
}


def get(persona_id: str) -> Persona:
    return PERSONAS[persona_id]
