from pathlib import Path

from backend.skills_loader import SkillRegistry


def test_registry_loads_seed_skills():
    reg = SkillRegistry.from_dir(Path(__file__).parents[2] / "skills")
    names = set(reg.names())
    assert {
        "peraturan_search",
        "pasal_lookup",
        "citation_trace",
        "contract_draft",
        "contract_review",
        "clause_library",
        "legal_memo",
    }.issubset(names)


def test_find_by_tool_resolves():
    reg = SkillRegistry.from_dir(Path(__file__).parents[2] / "skills")
    skill = reg.find_by_tool("peraturan_search")
    assert skill is not None
    assert skill.id == "peraturan_search"


def test_tools_for_persona():
    reg = SkillRegistry.from_dir(Path(__file__).parents[2] / "skills")
    tools = reg.tools_for(["peraturan_search", "pasal_lookup"])
    names = [t["name"] for t in tools]
    assert "peraturan_search" in names
    assert "pasal_lookup" in names
    # Anthropic shape
    assert all("input_schema" in t for t in tools)
