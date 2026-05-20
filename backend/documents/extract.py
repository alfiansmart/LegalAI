"""Extract plain text from uploaded files (PDF / DOCX / TXT / MD)."""
from __future__ import annotations

import io


def extract(filename: str, data: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return _extract_pdf(data)
    if name.endswith(".docx"):
        return _extract_docx(data)
    # txt / md / fallback
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="ignore")


def _extract_pdf(data: bytes) -> str:
    import pdfplumber

    parts: list[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:  # noqa: BLE001
                parts.append("")
    return "\n\n".join(p for p in parts if p).strip()


def _extract_docx(data: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text).strip()
