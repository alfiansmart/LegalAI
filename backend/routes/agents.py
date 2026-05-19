from fastapi import APIRouter

router = APIRouter()


@router.get("")
def list_agents() -> list[dict]:
    """Return built-in agent personas."""
    return [
        {
            "id": "asisten_hukum",
            "name": "Asisten Hukum",
            "description": "Asisten umum untuk Q&A peraturan Indonesia.",
            "skills": ["peraturan_search", "pasal_lookup", "citation_trace"],
        },
        {
            "id": "drafter",
            "name": "Drafter Kontrak",
            "description": "Membuat draft perjanjian dari template.",
            "skills": ["contract_draft", "clause_library", "pasal_lookup"],
        },
        {
            "id": "reviewer",
            "name": "Reviewer Kontrak",
            "description": "Review klausa, flag risiko, & compliance check.",
            "skills": ["contract_review", "clause_library", "peraturan_search"],
        },
        {
            "id": "researcher",
            "name": "Legal Researcher",
            "description": "Riset hukum mendalam dengan citation trace.",
            "skills": ["peraturan_search", "citation_trace", "legal_memo"],
        },
    ]
