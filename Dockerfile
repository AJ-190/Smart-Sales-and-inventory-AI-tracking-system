FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

# This image is the API only. Celery must run as SEPARATE containers from the
# same image, otherwise the beat schedule never fires and no debt reminder SMS
# is ever sent:
#
#   docker run ... celery -A src.celery_tasks.celery_app:celery worker --loglevel=info
#   docker run ... celery -A src.celery_tasks.celery_app:celery beat --loglevel=info
#
# Both need the same REDIS_URL and SMS_KEY env vars as the API.
