import logging
from src.config import get_settings
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from src.debts import models as dm

logger = logging.getLogger("scheduler")


def _build_jobstore() -> dict:
    """Return the persistent job store, or memory if SYNC_DATABASE_URL is unset."""
    sync_url = (get_settings().SYNC_DATABASE_URL or "").strip()
    if not sync_url:
        logger.warning(
            "SYNC_DATABASE_URL is not set; APScheduler jobs will not persist "
            "across restarts."
        )
        return {"default": MemoryJobStore()}

    try:
        return {
            "default": SQLAlchemyJobStore(
                url=sync_url,
                tablename="apscheduler_jobs",
                engine_options={"pool_pre_ping": True},
            )
        }
    except Exception as exc:
        logger.warning(
            "Could not create the APScheduler job store (%s); jobs will not "
            "persist across restarts.",
            exc,
        )
        return {"default": MemoryJobStore()}


executors = {"default": ThreadPoolExecutor(max_workers=29)}


MISFIRE_GRACE_TIME = 3 * 3600

job_defaults = {
    "coalesce": True,
    "max_instances": 3,
    "misfire_grace_time": MISFIRE_GRACE_TIME,
}

scheduler = BackgroundScheduler(
    jobstores=_build_jobstore(),
    executors=executors,
    job_defaults=job_defaults,
    timezone="Africa/Accra",
)
