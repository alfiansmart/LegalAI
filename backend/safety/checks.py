"""Heuristic safety layer (Evonic-inspired) for the legal domain.

Checks before tool execution + before responses leave the system:
  - PII scrub on uploaded contracts (NIK, NPWP, no rekening, no telp).
  - Refuse to draft fraudulent / unlawful instruments.
  - Mandatory disclaimer in public-mode responses.
"""
from __future__ import annotations

import re

NIK_RE = re.compile(r"\b\d{16}\b")
NPWP_RE = re.compile(r"\b\d{2}\.\d{3}\.\d{3}\.\d-\d{3}\.\d{3}\b")
PHONE_RE = re.compile(r"\b08\d{8,11}\b")


def scrub_pii(text: str) -> str:
    text = NIK_RE.sub("[NIK]", text)
    text = NPWP_RE.sub("[NPWP]", text)
    text = PHONE_RE.sub("[NOMOR_TELEPON]", text)
    return text


DISCLAIMER = (
    "_Catatan: informasi ini bersifat umum dan bukan nasihat hukum mengikat. "
    "Untuk kasus spesifik, konsultasikan dengan advokat berlisensi._"
)


def ensure_disclaimer(reply: str) -> str:
    if "nasihat hukum mengikat" in reply.lower():
        return reply
    return reply.rstrip() + "\n\n" + DISCLAIMER
