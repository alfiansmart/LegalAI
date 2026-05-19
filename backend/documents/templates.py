"""Jinja2-based template registry for document drafting.

Templates live in `/templates/*.md` (markdown with Jinja2 placeholders).
Each template id matches its filename stem.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound

from backend.config import get_settings


@dataclass(slots=True)
class TemplateInfo:
    id: str
    title: str
    description: str
    path: Path


_ENV: Environment | None = None


def _env() -> Environment:
    global _ENV
    if _ENV is None:
        tdir = Path(get_settings().templates_dir)
        _ENV = Environment(
            loader=FileSystemLoader(str(tdir)),
            autoescape=False,
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        _ENV.filters["id_date"] = _format_id_date
    return _ENV


def _format_id_date(d: date | str | None) -> str:
    if d is None:
        d = date.today()
    if isinstance(d, str):
        try:
            d = date.fromisoformat(d)
        except ValueError:
            return d
    bulan = [
        "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember",
    ]
    return f"{d.day} {bulan[d.month - 1]} {d.year}"


def render(template_id: str, params: dict[str, Any]) -> str:
    """Render a template by id with the given parameters.

    `params` is merged with sensible defaults (`tanggal`, `today`).
    """
    try:
        tmpl = _env().get_template(f"{template_id}.md")
    except TemplateNotFound as e:
        raise ValueError(f"template not found: {template_id!r}") from e
    merged: dict[str, Any] = {
        "tanggal": _format_id_date(date.today()),
        "today": date.today().isoformat(),
    }
    merged.update(params)
    return tmpl.render(**merged)


def list_templates() -> list[TemplateInfo]:
    tdir = Path(get_settings().templates_dir)
    out: list[TemplateInfo] = []
    if not tdir.exists():
        return out
    for p in sorted(tdir.glob("*.md")):
        if p.name.upper() == "README.MD":
            continue
        out.append(
            TemplateInfo(
                id=p.stem,
                title=_humanize(p.stem),
                description="",
                path=p,
            )
        )
    return out


def _humanize(slug: str) -> str:
    return slug.replace("_", " ").title()
