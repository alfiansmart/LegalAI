from celery import Celery

from backend.config import get_settings

settings = get_settings()

celery_app = Celery(
    "legalai",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "backend.corpus.tasks",
        "backend.flows.tasks",
        "backend.rag.tasks",
    ],
)

celery_app.conf.task_default_queue = "legalai"
celery_app.conf.timezone = "Asia/Jakarta"
