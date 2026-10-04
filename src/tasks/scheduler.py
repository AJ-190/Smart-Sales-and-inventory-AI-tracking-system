import logging
from src.config import get_settings
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from src.debts import models as dm

logger = logging.getLogger("scheduler")

scheduler = BackgroundScheduler()

jobs_store = {
    "default": SQLAlchemyJobStore(
        url=get_settings().SYNC_DATABASE_URL,
        tablename="apscheduler_jobs",
        engine_options={"pool_pre_ping": True},
    )
}

executors = {"default": ThreadPoolExecutor(max_workers=29)}

job_defaults = {
    "coalesce": False,
    "max_instances": 3,
    "executors": executors,
    "misfire_grace_time": 3 * 3600, 
}
