FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Celery has been replaced by APScheduler (src/tasks/), so there is no separate
# worker or beat container to start any more.
#
# NOTE: no startup hook calls start_report_schedulers() yet, so scheduled
# reports and hourly debt reminders do not fire in this image. See the
# "Scheduled Jobs Not Wired Up" section of README.md.
