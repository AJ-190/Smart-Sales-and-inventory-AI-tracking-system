web: python -m uvicorn src.main:app --host 0.0.0.0 --port $PORT
worker: celery -A src.celery_tasks.celery_app:celery worker --loglevel=info --concurrency=2
beat: celery -A src.celery_tasks.celery_app:celery beat --loglevel=info
