"""BPK scraper — fetch a peraturan record from peraturan.bpk.go.id.

BPK is the canonical primary source for Indonesian peraturan. Each
peraturan has a landing page with metadata + a PDF/HTML body. We
extract the body text + metadata and hand it to `parse_peraturan_text`
to build a ParsedPeraturan ready for the seed loader.

Architecture:
  - `fetch_html(url)` — HTTP GET (uses httpx, retries with backoff).
  - `parse_landing_page(html, url)` — pure-text: extract metadata
    (jenis / nomor / tahun / judul / tentang / penerbit) and a
    cleartext body. *No DB, no network — directly testable.*
  - `scrape_bpk_url(url)` — convenience: fetch → parse → return
    ParsedPeraturan.

Many BPK pages are SSR HTML; we only fall back to Playwright (heavy
dependency, already a project dep) when an SPA route refuses to render
server-side. For Phase 6 we cover the SSR path; the JS-heavy path
lives behind `scrape_bpk_url_browser` and is opt-in.

The parser tolerates variations in the BPK template — different
peraturan types (UU vs Perpres vs Permen) render slightly different
metadata blocks. We use anchor strings ("Nomor", "Tahun", "Tentang",
"Status") rather than fragile CSS selectors.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from backend.ingest.parsers.peraturan_text import ParsedPeraturan, parse_peraturan_text

_log = logging.getLogger(__name__)


# Maps the BPK "Jenis / Bentuk" label to our JenisPeraturan enum value.
_JENIS_MAP = {
    "undang-undang": "UU",
    "undang-undang dasar": "UUD",
    "uud": "UUD",
    "peraturan pemerintah pengganti undang-undang": "Perppu",
    "perppu": "Perppu",
    "peraturan pemerintah": "PP",
    "peraturan presiden": "Perpres",
    "peraturan menteri": "Permen",
    "peraturan daerah": "Perda",
    "kuhp": "KUHP",
    "kuhperdata": "KUHPerdata",
    "kuhap": "KUHAP",
}


@dataclass(slots=True)
class BPKFetchError(Exception):
    url: str
    message: str

    def __str__(self) -> str:  # pragma: no cover — trivial
        return f"BPKFetchError({self.url}): {self.message}"


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------


async def scrape_bpk_url(url: str, *, timeout: float = 30.0) -> ParsedPeraturan:
    """Fetch + parse a BPK landing page. Single-shot."""
    html = await fetch_html(url, timeout=timeout)
    return parse_landing_page(html, url=url)


async def fetch_html(url: str, *, timeout: float = 30.0, max_retries: int = 3) -> str:
    """HTTP GET with exponential backoff retry. Returns the response body."""
    import asyncio

    import httpx

    backoff = 1.0
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": "LegalAI/0.1 (Indonesian Legal Workspace; contact: dev@legalai.local)"
                },
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.text
        except Exception as e:  # noqa: BLE001
            last_err = e
            _log.warning("bpk fetch attempt %d failed: %s", attempt + 1, e)
            await asyncio.sleep(backoff)
            backoff *= 2
    raise BPKFetchError(url=url, message=str(last_err) if last_err else "unknown")


# -----------------------------------------------------------------------------
# Parser — pure-text, directly testable
# -----------------------------------------------------------------------------


def parse_landing_page(html: str, *, url: str | None = None) -> ParsedPeraturan:
    """Extract metadata + body text from BPK HTML.

    Robust against template drift: looks for labelled key/value
    fragments by anchor strings rather than fragile selectors.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")

    # Strip nav / scripts / footer for clean text extraction.
    for tag in soup.find_all(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    text = soup.get_text("\n", strip=False)
    text = re.sub(r"\n{3,}", "\n\n", text)

    meta = _extract_metadata_from_text(text)
    body = _extract_body_text(soup, text)

    return parse_peraturan_text(
        body,
        jenis=meta.get("jenis", "UU"),
        nomor=meta.get("nomor"),
        tahun=meta.get("tahun"),
        judul=meta.get("judul", ""),
        tentang=meta.get("tentang"),
        source_url=url,
    )


def _extract_metadata_from_text(text: str) -> dict:
    out: dict = {}

    # Anchor-based extraction. BPK metadata blocks look like:
    #   "Jenis / Bentuk Peraturan : UNDANG-UNDANG"
    #   "Nomor : 13"
    #   "Tahun : 2003"
    #   "Tentang : KETENAGAKERJAAN"
    for line in text.splitlines():
        m = _LABEL_VALUE_RE.match(line.strip())
        if not m:
            continue
        label = m["label"].lower().strip()
        value = m["value"].strip()
        if not value:
            continue
        if "jenis" in label or "bentuk" in label:
            out["jenis"] = _normalise_jenis(value)
        elif label == "nomor" or label.endswith("nomor"):
            out["nomor"] = value
        elif label == "tahun":
            try:
                out["tahun"] = int(re.search(r"\d{4}", value).group(0))
            except (AttributeError, ValueError):
                pass
        elif label == "tentang":
            out["tentang"] = value
        elif label == "judul":
            out["judul"] = value
        elif label == "penerbit" or label == "pemrakarsa":
            out["penerbit"] = value
        elif label == "status":
            out["status"] = "berlaku" if "berlaku" in value.lower() else value.lower()

    # Construct judul if missing.
    if not out.get("judul"):
        parts = []
        if out.get("jenis"):
            parts.append(out["jenis"])
        if out.get("nomor") and out.get("tahun"):
            parts.append(f"No. {out['nomor']} Tahun {out['tahun']}")
        if out.get("tentang"):
            parts.append(f"tentang {out['tentang']}")
        if parts:
            out["judul"] = " ".join(parts)
    return out


_LABEL_VALUE_RE = re.compile(
    r"^(?P<label>[A-Za-z][A-Za-z /]+?)\s*[:.]\s*(?P<value>.+)$"
)


def _normalise_jenis(value: str) -> str:
    """Map BPK's free-text jenis label to our enum value."""
    v = value.strip().lower()
    for key, mapped in _JENIS_MAP.items():
        if v == key or v.startswith(key + " ") or v.startswith(key + ":") or key in v:
            return mapped
    # Fallback: title-case the first token (e.g. "Permendag" → "Permendag").
    first = value.strip().split()[0] if value.strip() else "UU"
    return first[:1].upper() + first[1:].lower()


def _extract_body_text(soup, fallback_text: str) -> str:
    """Pull the peraturan body out of common BPK containers.

    BPK landing pages put the readable text in one of several
    containers depending on template version. We try a list of
    selectors and fall back to the full page text if none match.
    """
    for selector in [
        "#content-isi",
        ".isi-peraturan",
        ".document-body",
        ".content-detail",
        "main",
    ]:
        node = soup.select_one(selector)
        if node and len(node.get_text(strip=True)) > 200:
            return _normalise_body(node.get_text("\n", strip=False))
    return _normalise_body(fallback_text)


def _normalise_body(text: str) -> str:
    # Drop the metadata header so the parser only sees the pasal body.
    # Heuristic: find the first "BAB" or "Pasal 1" and start from there.
    m = re.search(r"^[ \t]*(?:BAB\s+[IVXLCDM\d]|Pasal\s+1\b)", text, re.M)
    if m:
        text = text[m.start():]
    # Collapse common BPK boilerplate footers.
    text = re.sub(r"©.*$", "", text, flags=re.M)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
