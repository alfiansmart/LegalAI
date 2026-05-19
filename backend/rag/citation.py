"""Parse Indonesian legal citations from free text.

Handles forms like:
    "Pasal 1320 KUHPerdata"
    "Pasal 1320 ayat (1) huruf a KUHPerdata"
    "Pasal 5 ayat (1) UU No. 13 Tahun 2003"
    "Pasal 27 Perpres 12/2021"

Returns structured records suitable for `pasal_lookup`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


# Order matters: more specific patterns first.
_KITAB = {
    "kuhperdata": "KUHPerdata",
    "kuh perdata": "KUHPerdata",
    "kuhp": "KUHP",
    "kuhap": "KUHAP",
    "uud": "UUD",
}

_PERATURAN_RE = re.compile(
    r"""
    (?P<jenis>UU|Perppu|PP|Perpres|Permen|Perda)
    \s* (?: No\.? \s* )?
    (?P<nomor>[A-Za-z0-9./-]+)
    \s* (?: Tahun \s* )?
    (?: / \s* )?
    (?P<tahun>\d{4})
    """,
    re.IGNORECASE | re.VERBOSE,
)

_PASAL_RE = re.compile(
    r"""
    Pasal \s+ (?P<pasal>\d+[A-Za-z]?)
    (?: \s+ ayat \s* \( \s* (?P<ayat>\d+[a-z]?) \s* \) )?
    (?: \s+ huruf \s+ (?P<huruf>[a-zA-Z]) )?
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass(slots=True)
class CitationRef:
    jenis: str | None = None
    nomor: str | None = None
    tahun: int | None = None
    pasal: str | None = None
    ayat: str | None = None
    huruf: str | None = None
    raw: str = ""


def parse_citations(text: str) -> list[CitationRef]:
    out: list[CitationRef] = []
    for m in _PASAL_RE.finditer(text):
        ref = CitationRef(
            pasal=m.group("pasal"),
            ayat=m.group("ayat"),
            huruf=m.group("huruf"),
            raw=m.group(0),
        )
        # look ahead for the source peraturan within 80 chars
        tail = text[m.end() : m.end() + 80]
        kitab = _detect_kitab(tail)
        if kitab:
            ref.jenis = kitab
        else:
            per = _PERATURAN_RE.search(tail)
            if per:
                ref.jenis = per.group("jenis").upper()
                ref.nomor = per.group("nomor")
                ref.tahun = int(per.group("tahun"))
        out.append(ref)
    return out


def _detect_kitab(s: str) -> str | None:
    low = s.lower()
    for k, v in _KITAB.items():
        if low.startswith(k) or f" {k}" in low[:20]:
            return v
    return None


def format_citation(r: CitationRef) -> str:
    parts = [f"Pasal {r.pasal}"]
    if r.ayat:
        parts.append(f"ayat ({r.ayat})")
    if r.huruf:
        parts.append(f"huruf {r.huruf}")
    if r.jenis in {"KUHP", "KUHPerdata", "KUHAP", "UUD"}:
        parts.append(r.jenis)
    elif r.jenis:
        parts.append(f"{r.jenis} {r.nomor}/{r.tahun}")
    return " ".join(parts)
