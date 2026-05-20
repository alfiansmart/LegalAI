"""JDIHN scraper — Indonesian government legal-info federation.

JDIHN (Jaringan Dokumentasi dan Informasi Hukum Nasional) federates
JDIH sites from ministries and provinces. Each anggota site shares a
fairly similar HTML template, with a metadata block and a body
section.

We use the same anchor-string extraction strategy as the BPK scraper
because the templates are close cousins. Callers point at any JDIHN
member URL and we attempt to parse it. Failures degrade gracefully —
the parser returns whatever metadata it could find and an empty
`pasal` list, which the caller can flag.

This file is intentionally small. JDIHN coverage is huge (provincial
Perda, ministry Permen) but quality varies; full per-site adapters can
be added over time as their templates are mapped.
"""
from __future__ import annotations

import logging

from backend.ingest.parsers.peraturan_text import ParsedPeraturan
from backend.ingest.scrapers.bpk import (
    BPKFetchError,
    fetch_html,
    parse_landing_page,
)

_log = logging.getLogger(__name__)


async def scrape_jdihn_url(url: str, *, timeout: float = 30.0) -> ParsedPeraturan:
    """Fetch + parse a JDIHN landing page. Same parser as BPK."""
    try:
        html = await fetch_html(url, timeout=timeout)
    except BPKFetchError as e:
        # Re-raise with clearer typing for callers who route differently.
        raise JDIHNFetchError(url=url, message=e.message) from e
    return parse_landing_page(html, url=url)


class JDIHNFetchError(Exception):
    def __init__(self, url: str, message: str) -> None:
        super().__init__(f"JDIHNFetchError({url}): {message}")
        self.url = url
        self.message = message
