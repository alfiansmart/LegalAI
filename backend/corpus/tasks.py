"""Celery tasks for the ingestion pipeline (fetch → parse → normalize → chunk → embed → index)."""
from __future__ import annotations

from backend.worker import celery_app


@celery_app.task(name="corpus.fetch_bpk")
def fetch_bpk(url: str) -> None:
    raise NotImplementedError


@celery_app.task(name="corpus.parse_pdf")
def parse_pdf(peraturan_id: int, pdf_path: str) -> None:
    raise NotImplementedError


@celery_app.task(name="corpus.normalize")
def normalize(peraturan_id: int) -> None:
    raise NotImplementedError
