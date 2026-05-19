"""Load skills from /skills/<name>/skill.json (Evonic-style)."""
from __future__ import annotations

import importlib.util
import inspect
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(slots=True)
class Skill:
    id: str
    name: str
    version: str
    description: str
    system_prompt: str
    tools: list[dict]
    handlers: dict[str, Callable[..., Any]]
    manifest: dict

    async def call(self, tool_name: str, args: dict, agent: Any = None) -> Any:
        if tool_name not in self.handlers:
            raise KeyError(f"Tool {tool_name!r} not implemented in skill {self.id!r}")
        result = self.handlers[tool_name](agent=agent, args=args)
        if inspect.iscoroutine(result):
            result = await result
        return result


class SkillRegistry:
    def __init__(self, skills: dict[str, Skill]):
        self._skills = skills
        # Build a flat (tool_name -> skill_id) index for fast dispatch.
        self._tool_index: dict[str, str] = {}
        for sid, skill in skills.items():
            for tool in skill.tools:
                tname = tool.get("function", {}).get("name") or tool.get("id")
                if tname:
                    self._tool_index[tname] = sid

    @classmethod
    def from_dir(cls, dir_path: str | Path) -> "SkillRegistry":
        skills: dict[str, Skill] = {}
        root = Path(dir_path)
        if not root.exists():
            return cls(skills)
        for skill_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            manifest_path = skill_dir / "skill.json"
            if not manifest_path.exists():
                continue
            try:
                skills[skill_dir.name] = _load_one(skill_dir)
            except Exception as e:  # noqa: BLE001
                print(f"[skills] failed to load {skill_dir.name}: {e}", file=sys.stderr)
        return cls(skills)

    def get(self, skill_id: str) -> Skill:
        return self._skills[skill_id]

    def all(self) -> list[Skill]:
        return list(self._skills.values())

    def names(self) -> list[str]:
        return list(self._skills.keys())

    def find_by_tool(self, tool_name: str) -> Skill | None:
        sid = self._tool_index.get(tool_name)
        return self._skills.get(sid) if sid else None

    def tools_for(self, skill_ids: list[str]) -> list[dict]:
        """Anthropic-format tool list collated from the given skills."""
        out: list[dict] = []
        seen: set[str] = set()
        for sid in skill_ids:
            sk = self._skills.get(sid)
            if not sk:
                continue
            for t in sk.tools:
                fn = t.get("function", {})
                name = fn.get("name")
                if not name or name in seen:
                    continue
                seen.add(name)
                out.append(
                    {
                        "name": name,
                        "description": fn.get("description", t.get("description", "")),
                        "input_schema": fn.get(
                            "parameters", {"type": "object", "properties": {}}
                        ),
                    }
                )
        return out


def _load_one(skill_dir: Path) -> Skill:
    manifest = json.loads((skill_dir / "skill.json").read_text())
    tools_file = skill_dir / manifest.get("tools_file", "tools.json")
    tools_raw = json.loads(tools_file.read_text()) if tools_file.exists() else []
    tools = tools_raw if isinstance(tools_raw, list) else tools_raw.get("tools", [])

    system_md = skill_dir / "SYSTEM.md"
    system_prompt = system_md.read_text() if system_md.exists() else ""

    handlers: dict[str, Callable] = {}
    backend_pkg = skill_dir / "backend" / "tools"
    if backend_pkg.exists():
        for py in backend_pkg.glob("*.py"):
            if py.name.startswith("_"):
                continue
            mod_name = f"_legalai_skill_{skill_dir.name}_{py.stem}"
            spec = importlib.util.spec_from_file_location(mod_name, py)
            if not spec or not spec.loader:
                continue
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)
            if hasattr(mod, "execute"):
                handlers[py.stem] = mod.execute

    return Skill(
        id=manifest["id"],
        name=manifest.get("name", manifest["id"]),
        version=manifest.get("version", "0.0.1"),
        description=manifest.get("description", ""),
        system_prompt=system_prompt,
        tools=tools,
        handlers=handlers,
        manifest=manifest,
    )


__all__ = ["Skill", "SkillRegistry"]
