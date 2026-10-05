import inspect
import pickle

import pytest

from src.tasks import jobs
from src.tasks.scheduler import scheduler


JOB_IDS = [
    "daily-report-job",
    "weekly-report-job",
    "monthly-report-job",
    "hourly-debt-reminder-job",
]


@pytest.fixture
def registered(monkeypatch):
    """Register the jobs against an in-memory store and return them by id."""
    from apscheduler.jobstores.memory import MemoryJobStore

    store = MemoryJobStore()
    monkeypatch.setattr(jobs, "scheduler", scheduler)
    monkeypatch.setattr(scheduler, "_jobstores", store)
    return jobs.start_report_schedulers().get_jobs()


@pytest.mark.parametrize("job_id", JOB_IDS)
def test_every_scheduled_job_is_registered(registered, job_id):
    assert job_id in {job.id for job in registered}


@pytest.mark.parametrize("job_id", JOB_IDS)
def test_job_targets_are_synchronous(registered, job_id):
    """A coroutine passed to add_job never runs under ThreadPoolExecutor.

    APScheduler calls the function, gets a coroutine object back and discards
    it, so the job reports a successful run while doing nothing.
    """
    job = next(j for j in registered if j.id == job_id)

    assert not inspect.iscoroutinefunction(job.func), (
        f"{job_id} is registered as a coroutine function and will never execute"
    )


@pytest.mark.parametrize("job_id", JOB_IDS)
def test_job_targets_are_importable_by_name(registered, job_id):
    """SQLAlchemyJobStore pickles the job, so lambdas and closures are out."""
    job = next(j for j in registered if j.id == job_id)

    assert job.func.__module__ == jobs.__name__
    pickle.loads(pickle.dumps(job.func))


@pytest.mark.parametrize(
    "wrapper,coroutine",
    [
        ("run_daily_report", "daily_report_task"),
        ("run_weekly_report", "weekly_report_task"),
        ("run_monthly_report", "monthly_report_task"),
        ("run_debt_reminders", "process_due_reminders"),
    ],
)
def test_wrapper_actually_drives_the_coroutine(monkeypatch, wrapper, coroutine):
    """The sync wrapper must run the coroutine body, not just return one."""
    ran = []

    async def spy(*args, **kwargs):
        ran.append(True)
        return "done"

    monkeypatch.setattr(jobs, coroutine, spy)

    getattr(jobs, wrapper)()
    assert ran, f"{wrapper} returned without executing {coroutine}"


def test_scheduler_executor_runs_the_wrapper(monkeypatch):
    """End to end through the real executor, the way APScheduler calls it."""
    import time

    from apscheduler.executors.pool import ThreadPoolExecutor
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger

    ran = []

    async def spy():
        ran.append(True)

    monkeypatch.setattr(jobs, "process_due_reminders", spy)

    probe = BackgroundScheduler(
        jobstores={"default": __import__(
            "apscheduler.jobstores.memory", fromlist=["MemoryJobStore"]
        ).MemoryJobStore()},
        executors={"default": ThreadPoolExecutor(max_workers=2)},
    )
    probe.start()
    probe.add_job(jobs.run_debt_reminders, IntervalTrigger(seconds=1), id="probe")
    time.sleep(3.5)
    probe.shutdown(wait=False)

    assert ran, "executor did not run the wrapped coroutine"