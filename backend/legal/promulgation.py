"""Parse promulgation metadata + status clauses from peraturan text.

Every Indonesian peraturan ends with a stylised closing block ("penutup")
that carries the ground-truth answers to:

  - When was it enacted?       ("Ditetapkan di X pada tanggal Y")
  - When was it promulgated?   ("Diundangkan di X pada tanggal Y")
  - Which State Gazette entry? ("Lembaran Negara ... Nomor ... Tahun ...")
  - What does it kill?         ("dicabut dan dinyatakan tidak berlaku")
  - What does it amend?        ("sebagaimana telah diubah dengan ...")
  - When does it take effect?  ("mulai berlaku pada tanggal diundangkan",
                                 "berlaku 30 hari sejak diundangkan", ...)

This module is pure-text and side-effect-free so it's trivially testable.
The ingest orchestrator calls it once per peraturan and persists the
results onto the Peraturan row + emits CitationEdge rows for the
dicabut/diubah links.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date


# -----------------------------------------------------------------------------
# Indonesian month names → numbers (for "pada tanggal X bulan Y tahun Z")
# -----------------------------------------------------------------------------

_MONTHS_ID = {
    "januari": 1,
    "februari": 2,
    "pebruari": 2,  # archaic spelling still seen in older peraturan
    "maret": 3,
    "april": 4,
    "mei": 5,
    "juni": 6,
    "juli": 7,
    "agustus": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "desember": 12,
}


@dataclass
class ParsedPromulgation:
    ditetapkan_di: str | None = None
    tanggal_ditetapkan: date | None = None
    diundangkan_di: str | None = None
    tanggal_diundangkan: date | None = None
    lembaran_negara: str | None = None
    tambahan_lembaran_negara: str | None = None
    berita_negara: str | None = None
    effective_from: date | None = None
    # Raw textual references to peraturan this row affects. The caller
    # resolves them via pasal_as_of / peraturan lookup to insert
    # CitationEdge(kind=REPEALS|AMENDS) rows.
    repealed_refs: list[str] = field(default_factory=list)
    amended_refs: list[str] = field(default_factory=list)


# -----------------------------------------------------------------------------
# Date parsing
# -----------------------------------------------------------------------------

# "pada tanggal 25 Maret 2003" / "tanggal 25 Maret 2003"
_DATE_RE = re.compile(
    r"(?:pada\s+)?tanggal\s+(?P<d>\d{1,2})\s+(?P<m>[A-Za-z]+)\s+(?P<y>\d{4})",
    re.I,
)


def _parse_id_date(text: str) -> date | None:
    m = _DATE_RE.search(text)
    if not m:
        return None
    try:
        day = int(m["d"])
        month = _MONTHS_ID.get(m["m"].lower())
        year = int(m["y"])
        if not month:
            return None
        return date(year, month, day)
    except (TypeError, ValueError):
        return None


# -----------------------------------------------------------------------------
# Place parsing
# -----------------------------------------------------------------------------

# "Ditetapkan di Jakarta pada tanggal 25 Maret 2003"
_DITETAPKAN_RE = re.compile(
    r"Ditetapkan\s+di\s+(?P<place>[A-Z][A-Za-z .,'–-]+?)\s+(?:pada|tanggal|$)",
    re.I,
)
_DIUNDANGKAN_RE = re.compile(
    r"Diundangkan\s+di\s+(?P<place>[A-Z][A-Za-z .,'–-]+?)\s+(?:pada|tanggal|$)",
    re.I,
)


def _extract_place(pattern: re.Pattern, text: str) -> str | None:
    m = pattern.search(text)
    if not m:
        return None
    place = m["place"].strip().rstrip(",").strip()
    return place or None


def _extract_date_after(anchor_re: re.Pattern, text: str) -> date | None:
    """Find the anchor regex (Ditetapkan / Diundangkan), then look for
    a date on the same or following lines."""
    m = anchor_re.search(text)
    if not m:
        return None
    # Look at the 200 chars following the anchor.
    window = text[m.start() : m.end() + 200]
    return _parse_id_date(window)


# -----------------------------------------------------------------------------
# Lembaran Negara / Berita Negara
# -----------------------------------------------------------------------------

# "Lembaran Negara Republik Indonesia Tahun 2003 Nomor 39"
_LN_RE = re.compile(
    r"Lembaran\s+Negara(?:\s+Republik\s+Indonesia)?\s+(?:Tahun\s+(?P<year>\d{4})\s+)?Nomor\s+(?P<no>\d+)(?:\s+Tahun\s+(?P<year2>\d{4}))?",
    re.I,
)

# "Tambahan Lembaran Negara Republik Indonesia Nomor 4279"
_TLN_RE = re.compile(
    r"Tambahan\s+Lembaran\s+Negara(?:\s+Republik\s+Indonesia)?\s+Nomor\s+(?P<no>\d+)",
    re.I,
)

# "Berita Negara Republik Indonesia Tahun 2021 Nomor 1234"
_BN_RE = re.compile(
    r"Berita\s+Negara(?:\s+Republik\s+Indonesia)?\s+(?:Tahun\s+(?P<year>\d{4})\s+)?Nomor\s+(?P<no>\d+)(?:\s+Tahun\s+(?P<year2>\d{4}))?",
    re.I,
)


def _extract_ln(text: str) -> str | None:
    m = _LN_RE.search(text)
    if not m:
        return None
    year = m["year"] or m["year2"]
    no = m["no"]
    if year:
        return f"LN {year} No. {no}"
    return f"LN No. {no}"


def _extract_tln(text: str) -> str | None:
    m = _TLN_RE.search(text)
    if not m:
        return None
    return f"TLN No. {m['no']}"


def _extract_bn(text: str) -> str | None:
    m = _BN_RE.search(text)
    if not m:
        return None
    year = m["year"] or m["year2"]
    no = m["no"]
    if year:
        return f"BN {year} No. {no}"
    return f"BN No. {no}"


# -----------------------------------------------------------------------------
# Effective date — derived from "mulai berlaku" clauses
# -----------------------------------------------------------------------------

# "Peraturan ini mulai berlaku pada tanggal diundangkan."
_EFF_ON_PROMULGATION_RE = re.compile(
    r"mulai\s+berlaku\s+(?:pada\s+)?tanggal\s+diundangkan", re.I
)
# "Peraturan ini mulai berlaku 30 (tiga puluh) hari sejak tanggal diundangkan."
_EFF_DAYS_AFTER_RE = re.compile(
    r"mulai\s+berlaku\s+(?P<n>\d+)\s+(?:\([\w\s]+\)\s+)?hari\s+sejak\s+(?:tanggal\s+)?diundangkan",
    re.I,
)
# "Peraturan ini mulai berlaku pada tanggal 1 Januari 2024."
_EFF_EXPLICIT_DATE_RE = re.compile(
    r"mulai\s+berlaku\s+(?:pada\s+)?tanggal\s+(?P<d>\d{1,2})\s+(?P<m>[A-Za-z]+)\s+(?P<y>\d{4})",
    re.I,
)


def _extract_effective_from(text: str, tanggal_diundangkan: date | None) -> date | None:
    explicit = _EFF_EXPLICIT_DATE_RE.search(text)
    if explicit:
        return _parse_id_date(explicit.group(0))
    if _EFF_ON_PROMULGATION_RE.search(text):
        return tanggal_diundangkan
    delayed = _EFF_DAYS_AFTER_RE.search(text)
    if delayed and tanggal_diundangkan:
        try:
            from datetime import timedelta

            return tanggal_diundangkan + timedelta(days=int(delayed["n"]))
        except (TypeError, ValueError):
            return tanggal_diundangkan
    return None


# -----------------------------------------------------------------------------
# Repeal / amend reference extraction
# -----------------------------------------------------------------------------

# References to other peraturan inside a repeal/amend clause. The regex
# captures both the jenis token and the no/year so the caller can
# resolve to a Peraturan row.
_PERATURAN_REF_RE = re.compile(
    r"""
    \b(?P<jenis>UUD|Undang-Undang|UU|Perppu|Peraturan\s+Pemerintah\s+Pengganti\s+Undang-Undang|
       Peraturan\s+Pemerintah|PP|Peraturan\s+Presiden|Perpres|Peraturan\s+Menteri|Permen[a-z]*|
       Peraturan\s+Daerah|Perda|POJK|PBI|Perma|Tap\s+MPR|TAP\s+MPR|Qanun)
    \s*(?:Republik\s+Indonesia\s+)?
    (?:Nomor|No\.?)?\s*
    (?P<no>\d+[A-Za-z/.\-]*)
    \s*(?:Tahun\s*|/\s*)
    (?P<year>\d{4})
    """,
    re.I | re.X,
)


def _extract_peraturan_refs_in_window(window: str) -> list[str]:
    out: list[str] = []
    for m in _PERATURAN_REF_RE.finditer(window):
        jenis = re.sub(r"\s+", " ", m["jenis"]).strip()
        out.append(f"{jenis} No. {m['no']} Tahun {m['year']}")
    return out


# "Dengan berlakunya Peraturan Pemerintah ini, Peraturan Pemerintah Nomor X
#  Tahun Y dicabut dan dinyatakan tidak berlaku."
_REPEAL_CLAUSE_RE = re.compile(
    r"""
    (?:dengan\s+berlakunya\s+[^.]+?,\s*)?
    (?P<body>[^.]*?)
    (?:dicabut(?:\s+dan\s+dinyatakan\s+tidak\s+berlaku)?|dinyatakan\s+tidak\s+berlaku)
    """,
    re.I | re.X | re.S,
)

_AMEND_CLAUSE_RE = re.compile(
    r"""
    sebagaimana\s+(?:telah\s+)?(?:beberapa\s+kali\s+)?(?:diubah|dirubah)\s+(?:dengan|terakhir\s+dengan)
    \s+(?P<body>[^.]+)
    """,
    re.I | re.X,
)


def _extract_repealed_refs(text: str) -> list[str]:
    out: list[str] = []
    for m in _REPEAL_CLAUSE_RE.finditer(text):
        out.extend(_extract_peraturan_refs_in_window(m["body"]))
    # De-dup preserving order.
    seen: set[str] = set()
    deduped: list[str] = []
    for r in out:
        if r not in seen:
            seen.add(r)
            deduped.append(r)
    return deduped


def _extract_amended_refs(text: str) -> list[str]:
    out: list[str] = []
    for m in _AMEND_CLAUSE_RE.finditer(text):
        out.extend(_extract_peraturan_refs_in_window(m["body"]))
    seen: set[str] = set()
    deduped: list[str] = []
    for r in out:
        if r not in seen:
            seen.add(r)
            deduped.append(r)
    return deduped


# -----------------------------------------------------------------------------
# Public entry point
# -----------------------------------------------------------------------------


def parse_promulgation(text: str) -> ParsedPromulgation:
    """Parse the closing block of a peraturan into structured metadata.

    Tolerant of partial input — every field is optional. Returns an
    empty ParsedPromulgation when nothing matches; never raises.
    """
    result = ParsedPromulgation()
    if not text:
        return result

    result.ditetapkan_di = _extract_place(_DITETAPKAN_RE, text)
    result.tanggal_ditetapkan = _extract_date_after(_DITETAPKAN_RE, text)
    result.diundangkan_di = _extract_place(_DIUNDANGKAN_RE, text)
    result.tanggal_diundangkan = _extract_date_after(_DIUNDANGKAN_RE, text)

    result.lembaran_negara = _extract_ln(text)
    result.tambahan_lembaran_negara = _extract_tln(text)
    result.berita_negara = _extract_bn(text)

    result.effective_from = _extract_effective_from(
        text, result.tanggal_diundangkan
    )

    result.repealed_refs = _extract_repealed_refs(text)
    result.amended_refs = _extract_amended_refs(text)
    return result
