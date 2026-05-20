"""Parse plain-text Indonesian peraturan into a structured tree.

Most JDIH sites expose peraturan as either:
  - a clean text/PDF document, or
  - HTML with the body in a single <div> per pasal.

Either way, by the time we hit the parser we have a single string. We
walk it with the same heading patterns the document-outline parser
uses, but build a `Peraturan-shape` dict (jenis / nomor / tahun /
judul / pasal[] / ayat[] / huruf[]) — exactly the format the seed
loader already understands.

This keeps the ingest path identical whether the source is a hand-
curated seed JSON, a BPK scrape, or a JDIHN scrape. The scrapers only
need to (a) fetch the page, (b) extract the cleartext body, and
(c) populate metadata; this module does the structural parsing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Heading patterns (mirror backend.rag.doc_structure but produce a
# peraturan-shaped output, not an outline tree).
_BAB_RE = re.compile(
    r"^[ \t]*BAB\s+(?P<n>[IVXLCDM]+|\d+|[A-Z]+)\b[ \t]*(?P<title>.*)$", re.M
)
_BAGIAN_RE = re.compile(
    r"^[ \t]*Bagian\s+(?P<n>Kesatu|Kedua|Ketiga|Keempat|Kelima|Keenam|Ketujuh|Kedelapan|Kesembilan|Kesepuluh|\d+)\b[ \t]*(?P<title>.*)$",
    re.M | re.I,
)
_PASAL_RE = re.compile(r"^[ \t]*Pasal\s+(?P<n>\d+[A-Z]?)\b[ \t]*$", re.M)
# Ayat: "(1) text..." (single-digit or letter suffixes like 2a).
_AYAT_RE = re.compile(r"^\s*\(\s*(?P<n>\d+[a-z]?)\s*\)\s*(?P<rest>.*)$", re.M)
# Huruf: "a. text..."
_HURUF_RE = re.compile(r"^\s*(?P<h>[a-z])\.\s+(?P<rest>.*)$", re.M)


@dataclass
class ParsedPasal:
    nomor: str
    teks: str = ""
    ayat: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ParsedPeraturan:
    jenis: str
    nomor: str | None
    tahun: int | None
    judul: str
    tentang: str | None = None
    status: str = "berlaku"
    penerbit: str | None = None
    source_url: str | None = None
    pasal: list[ParsedPasal] = field(default_factory=list)

    def to_seed_dict(self) -> dict[str, Any]:
        """Serialise to the seed_loader's expected JSON shape."""
        return {
            "jenis": self.jenis,
            "nomor": self.nomor,
            "tahun": self.tahun,
            "judul": self.judul,
            "tentang": self.tentang,
            "status": self.status,
            "penerbit": self.penerbit,
            "source_url": self.source_url,
            "pasal": [
                {
                    "nomor": p.nomor,
                    "teks": p.teks,
                    "ayat": p.ayat,
                }
                for p in self.pasal
            ],
        }


def parse_pasal_bodies(text: str) -> list[ParsedPasal]:
    """Split a peraturan body into Pasal-level chunks, then parse each.

    Returns one ParsedPasal per Pasal heading. Body text between Pasal
    headings is attributed to the preceding Pasal. Ayat/Huruf inside
    that body get pulled out as nested structures.
    """
    matches = list(_PASAL_RE.finditer(text))
    if not matches:
        return []

    out: list[ParsedPasal] = []
    for i, m in enumerate(matches):
        nomor = m["n"]
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()

        pasal = ParsedPasal(nomor=nomor)
        _split_pasal_body(body, pasal)
        out.append(pasal)
    return out


def _split_pasal_body(body: str, pasal: ParsedPasal) -> None:
    """Within a Pasal's body, identify Ayat and Huruf structures."""
    ayat_matches = list(_AYAT_RE.finditer(body))
    if not ayat_matches:
        # Pasal-without-ayat: the whole body is the pasal text.
        pasal.teks = _collapse(body)
        return

    # Text before the first ayat is the pasal teks (the "lead-in").
    first_ayat_start = ayat_matches[0].start()
    pasal.teks = _collapse(body[:first_ayat_start])

    for i, m in enumerate(ayat_matches):
        ayat_n = m["n"]
        first_line = (m["rest"] or "").strip()
        ayat_body_start = m.end()
        ayat_body_end = ayat_matches[i + 1].start() if i + 1 < len(ayat_matches) else len(body)
        ayat_body = body[ayat_body_start:ayat_body_end]
        ayat_text, hurufs = _split_ayat_body(first_line, ayat_body)

        ayat_dict: dict[str, Any] = {
            "nomor": ayat_n,
            "teks": ayat_text,
        }
        if hurufs:
            ayat_dict["huruf"] = hurufs
        pasal.ayat.append(ayat_dict)


def _split_ayat_body(first_line: str, body: str) -> tuple[str, list[dict[str, str]]]:
    """Within one Ayat, peel off any `a. b. c.` Huruf list."""
    full = (first_line + "\n" + body).strip()
    huruf_matches = list(_HURUF_RE.finditer(full))
    if not huruf_matches:
        return _collapse(full), []

    text_before_huruf = full[: huruf_matches[0].start()].strip()
    hurufs: list[dict[str, str]] = []
    for i, m in enumerate(huruf_matches):
        h_letter = m["h"]
        h_body_start = m.end()
        h_body_end = huruf_matches[i + 1].start() if i + 1 < len(huruf_matches) else len(full)
        h_text = ((m["rest"] or "") + " " + full[h_body_start:h_body_end]).strip()
        hurufs.append({"huruf": h_letter, "teks": _collapse(h_text)})
    return _collapse(text_before_huruf), hurufs


def _collapse(s: str) -> str:
    # Collapse multiple whitespace into single spaces; preserve paragraph
    # breaks via a single newline.
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n[ \t]+", "\n", s)
    s = re.sub(r"\n{2,}", "\n", s)
    return s.strip()


def parse_peraturan_text(
    text: str,
    *,
    jenis: str,
    nomor: str | None = None,
    tahun: int | None = None,
    judul: str = "",
    tentang: str | None = None,
    source_url: str | None = None,
) -> ParsedPeraturan:
    """End-to-end: cleartext → ParsedPeraturan."""
    pasal_list = parse_pasal_bodies(text)
    return ParsedPeraturan(
        jenis=jenis,
        nomor=nomor,
        tahun=tahun,
        judul=judul,
        tentang=tentang,
        source_url=source_url,
        pasal=pasal_list,
    )
