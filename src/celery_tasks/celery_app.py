from celery import Celery
from src.config import get_settings

celery = Celery(
    "worker",
    broker=get_settings().REDIS_URL,
    backend=get_settings().REDIS_URL
)


celery.conf.update(
    task_serializer="json",
    accept_content=['json'],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True
)

