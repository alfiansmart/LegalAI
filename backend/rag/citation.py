"""Parse Indonesian legal citations from free text.

Handles forms like:
    "Pasal 1320 KUHPerdata"
    "Pasal 1320 ayat (1) huruf a KUHPerdata"
    "Pasal 5 ayat (1) UU No. 13 Tahun 2003"
    "Pasal 27 Perpres 12/2021"
    "Pasal 4 POJK No. 11/POJK.03/2020"
    "Pasal 5 Tap MPR No. I/MPR/2003"
    "Putusan MK No. 25/PUU-XIV/2016"
    "Pasal 8 Permenaker No. 6 Tahun 2020"

Returns structured records suitable for `pasal_lookup`.

When the source peraturan is recognised by name but its nomor/tahun
follows an idiosyncratic format (POJK's slash-separated multi-part
nomor, Tap MPR's roman-numeral session, Putusan's PUU register), the
parser captures the raw nomor verbatim — the database lookup layer
matches by the same string so re-formatting isn't required.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


# Kitab matchers — single-token sources where there is no nomor/tahun.
_KITAB = {
    "kuhperdata": "KUHPerdata",
    "kuh perdata": "KUHPerdata",
    "kuhp": "KUHP",
    "kuhap": "KUHAP",
    "uud": "UUD",
}


# Standard peraturan with a numeric nomor + 4-digit tahun. Covers
# UU / Perppu / PP / Perpres / Perda / Permen (generic) / Permen-with-
# ministry-suffix (Permendag, Permenkeu, Permenkes, …) / Qanun /
# Perda Provinsi / Perda Kab.
_PERATURAN_RE = re.compile(
    r"""
    (?P<jenis>
        UU | Perppu | PP | Perpres |
        Perda(?:\s+(?:Provinsi|Prov|Kabupaten|Kab|Kota))? |
        Permen[a-z]* |             # Permen, Permendag, Permenkeu, …
        Peraturan\s+Menteri(?:\s+(?!No\b|Nomor\b)[A-Za-z]+){0,4} |
        Peraturan\s+Daerah |
        Peraturan\s+Pemerintah(?:\s+Pengganti\s+Undang-Undang)? |
        Peraturan\s+Presiden |
        Qanun
    )
    \s* (?: Republik \s+ Indonesia \s* )?
    (?: No\.? \s* | Nomor \s+ )
    (?P<nomor>[A-Za-z0-9./-]+)
    \s* (?: Tahun \s* )?
    (?: / \s* )?
    (?P<tahun>\d{4})
    """,
    re.IGNORECASE | re.VERBOSE,
)


# POJK / PBI / PADG / Perma / SEMA / PerMK / Per-KPU — these often use
# multi-segment nomor like "11/POJK.03/2020" or "I/MPR/2003".
_BODY_PERATURAN_RE = re.compile(
    r"""
    (?P<jenis>POJK | PBI | PADG | Perma | SEMA | PerMK | Per[-]?KPU |
              Tap\s+MPR | TAP\s+MPR | Ketetapan\s+MPR)
    \s* (?: No\.? \s* | Nomor \s+ )?
    (?P<nomor>[IVXLCDM0-9][A-Za-z0-9./.\-]*?)
    \s* (?: Tahun \s* | / \s* )
    (?P<tahun>\d{4})
    """,
    re.IGNORECASE | re.VERBOSE,
)


# Putusan MK / Putusan MA — register format: "No. 25/PUU-XIV/2016",
# "No. 003/PUU-IV/2006", "Putusan MA No. 1234 K/Pdt/2020".
_PUTUSAN_RE = re.compile(
    r"""
    (?P<jenis>Putusan\s+M(?:K|A))
    \s* (?: No\.? \s* | Nomor \s+ )?
    (?P<nomor>\d+[A-Za-z./\-]*(?:/[A-Za-z\-]+)*)
    \s* (?: / \s* )
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


# Normalise a free-text jenis token to our JenisPeraturan enum value.
_JENIS_NORMALISE = {
    "uu": "UU",
    "undang-undang": "UU",
    "perppu": "Perppu",
    "peraturan pemerintah pengganti undang-undang": "Perppu",
    "pp": "PP",
    "peraturan pemerintah": "PP",
    "perpres": "Perpres",
    "peraturan presiden": "Perpres",
    "perda": "Perda",
    "perda provinsi": "PerdaProv",
    "perda prov": "PerdaProv",
    "perda kabupaten": "PerdaKab",
    "perda kab": "PerdaKab",
    "perda kota": "PerdaKab",
    "peraturan daerah": "Perda",
    "qanun": "Qanun",
    "uud": "UUD",
    "tap mpr": "TapMPR",
    "ketetapan mpr": "TapMPR",
    "pojk": "POJK",
    "pbi": "PBI",
    "padg": "PADG",
    "perma": "Perma",
    "sema": "SEMA",
    "permk": "PerMK",
    "perkpu": "PerKPU",
    "per-kpu": "PerKPU",
    "putusan mk": "PutusanMK",
    "putusan ma": "PutusanMA",
}


def _normalise_jenis(raw: str) -> tuple[str, str | None]:
    """Return (canonical_jenis, kementerian_subtype_or_None).

    A "Permenaker" / "Permendag" token returns ("Permen", "Tenaga Kerja" /
    "Perdagangan"), so downstream code can record the ministry on the
    Peraturan.kementerian column without losing the discriminator.
    """
    s = re.sub(r"\s+", " ", raw).strip().lower()
    # Direct hit on the normalisation table.
    if s in _JENIS_NORMALISE:
        return _JENIS_NORMALISE[s], None
    # "Peraturan Menteri Tenaga Kerja" → ("Permen", "Tenaga Kerja")
    if s.startswith("peraturan menteri"):
        kem = s[len("peraturan menteri") :].strip().title() or None
        return "Permen", kem
    # "Permendag" / "Permenkeu" / "Permenkes" / "Permenaker" / "Permendikbud"
    if s.startswith("permen") and s != "permen":
        return "Permen", _ministry_for_permen_suffix(s)
    # Fall back to title-case form.
    return raw.strip(), None


_MINISTRY_BY_SUFFIX = {
    "permendag": "Perdagangan",
    "permenkeu": "Keuangan",
    "permenkes": "Kesehatan",
    "permenaker": "Tenaga Kerja",
    "permendikbud": "Pendidikan dan Kebudayaan",
    "permendagri": "Dalam Negeri",
    "permenkominfo": "Komunikasi dan Informatika",
    "permenkumham": "Hukum dan HAM",
    "permenhub": "Perhubungan",
    "permentan": "Pertanian",
    "permenperin": "Perindustrian",
    "permen esdm": "Energi dan Sumber Daya Mineral",
    "permenlhk": "Lingkungan Hidup dan Kehutanan",
    "permenpora": "Pemuda dan Olahraga",
    "permensos": "Sosial",
    "permendes": "Desa, PDT dan Transmigrasi",
    "permendesa": "Desa, PDT dan Transmigrasi",
    "permenpan": "PAN-RB",
    "permenpanrb": "PAN-RB",
}


def _ministry_for_permen_suffix(token: str) -> str | None:
    return _MINISTRY_BY_SUFFIX.get(token)


@dataclass(slots=True)
class CitationRef:
    jenis: str | None = None
    nomor: str | None = None
    tahun: int | None = None
    pasal: str | None = None
    ayat: str | None = None
    huruf: str | None = None
    raw: str = ""
    kementerian: str | None = None  # populated for Permen sub-types


def _scan_source(tail: str) -> tuple[str, str | None, int | None, str | None] | None:
    """Find the source peraturan in a tail string. Tries each pattern in
    specificity order. Returns (canonical_jenis, nomor, tahun, kementerian)
    or None when no source matches.
    """
    # Putusan first — its nomor format collides with the standard re.
    pu = _PUTUSAN_RE.search(tail)
    if pu:
        canon, _ = _normalise_jenis(pu.group("jenis"))
        return canon, pu.group("nomor"), int(pu.group("tahun")), None
    # Body-issued (POJK/PBI/PerMA/Tap MPR/…) before the standard pattern
    # because their nomor format includes slashes the standard regex
    # would split incorrectly.
    bp = _BODY_PERATURAN_RE.search(tail)
    if bp:
        canon, kem = _normalise_jenis(bp.group("jenis"))
        return canon, bp.group("nomor"), int(bp.group("tahun")), kem
    # Standard nomor/tahun forms.
    per = _PERATURAN_RE.search(tail)
    if per:
        canon, kem = _normalise_jenis(per.group("jenis"))
        return canon, per.group("nomor"), int(per.group("tahun")), kem
    return None


def parse_citations(text: str) -> list[CitationRef]:
    out: list[CitationRef] = []
    for m in _PASAL_RE.finditer(text):
        ref = CitationRef(
            pasal=m.group("pasal"),
            ayat=m.group("ayat"),
            huruf=m.group("huruf"),
            raw=m.group(0),
        )
        # look ahead for the source peraturan within 100 chars
        tail = text[m.end() : m.end() + 100]
        kitab = _detect_kitab(tail)
        if kitab:
            ref.jenis = kitab
        else:
            scanned = _scan_source(tail)
            if scanned:
                ref.jenis, ref.nomor, ref.tahun, ref.kementerian = scanned
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
    elif r.jenis in {"TapMPR"}:
        parts.append(f"Tap MPR No. {r.nomor}/{r.tahun}")
    elif r.jenis in {"PutusanMK", "PutusanMA"}:
        kind = "MK" if r.jenis == "PutusanMK" else "MA"
        parts.append(f"Putusan {kind} No. {r.nomor}/{r.tahun}")
    elif r.jenis == "Permen" and r.kementerian:
        parts.append(f"Permen {r.kementerian} No. {r.nomor}/{r.tahun}")
    elif r.jenis:
        parts.append(f"{r.jenis} {r.nomor}/{r.tahun}")
    return " ".join(parts)
