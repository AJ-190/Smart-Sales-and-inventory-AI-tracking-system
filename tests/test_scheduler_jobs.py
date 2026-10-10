import inspect
import pickle
from datetime import datetime, timedelta, timezone

import pytest
from apscheduler.job import Job
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.triggers.interval import IntervalTrigger

from src.tasks import debt_reminders, jobs
from src.tasks.scheduler import scheduler


JOB_IDS = [
    "daily-report-job",
    "weekly-report-job",
    "monthly-report-job",
    "hourly-debt-reminder-job",
]


@pytest.fixture
def registered(monkeypatch):
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

    job = next(j for j in registered if j.id == job_id)

    assert not inspect.iscoroutinefunction(job.func), (
        f"{job_id} is registered as a coroutine function and will never execute"
    )


@pytest.mark.parametrize("job_id", JOB_IDS)
def test_job_targets_are_importable_by_name(registered, job_id):
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


def test_jobs_do_not_borrow_the_request_pool():
    """Jobs run on their own loop, so they must not use the pooled engine.

    Every wrapper calls asyncio.run(), which builds a fresh event loop. A
    pooled asyncpg connection belongs to the loop that opened it, so handing
    one to a job raises "got Future attached to a different loop". This is the
    bug that made every scheduled job fail in production while the admin
    endpoint still returned 200.
    """
    from sqlalchemy.pool import NullPool

    from src.db.database import engine, job_engine

    assert isinstance(job_engine.pool, NullPool), (
        "job_engine must use NullPool; a shared pool leaks connections across "
        "the loops asyncio.run() creates"
    )
    assert job_engine is not engine, "jobs must not share the request engine"

    for module in (jobs, debt_reminders):
        shared = [
            name
            for name, value in vars(module).items()
            if getattr(value, "bind", None) is engine
        ]
        assert not shared, (
            f"{module.__name__} still references the pooled request engine "
            f"as {shared}"
        )


COROUTINE_BY_WRAPPER = {
    "run_daily_report": "daily_report_task",
    "run_weekly_report": "weekly_report_task",
    "run_monthly_report": "monthly_report_task",
    "run_debt_reminders": "process_due_reminders",
}


@pytest.mark.parametrize("wrapper", list(COROUTINE_BY_WRAPPER))
def test_wrapper_disposes_the_job_engine(monkeypatch, wrapper):
    """The loop dies with the job, so its connections must not outlive it."""
    disposed = []

    class _StubEngine:
        """AsyncEngine.dispose is read-only, so swap the whole engine out."""

        async def dispose(self):
            disposed.append(True)

    async def spy(*args, **kwargs):
        return "done"

    monkeypatch.setattr(jobs, "job_engine", _StubEngine())
    monkeypatch.setattr(jobs, COROUTINE_BY_WRAPPER[wrapper], spy)

    getattr(jobs, wrapper)()
    assert disposed, f"{wrapper} left the job engine undisposed"


def _stopped_scheduler(monkeypatch):
    """A scheduler over its own store that is never started, like a cold boot."""
    from apscheduler.schedulers.background import BackgroundScheduler

    store = MemoryJobStore()
    probe = BackgroundScheduler(
        jobstores={"default": store},
        timezone="Africa/Accra",
    )
    monkeypatch.setattr(jobs, "scheduler", probe)
    return probe, store


def _seed(probe, store, next_run_time):
    """Write one job row into the store without starting a scheduler."""
    job = Job(
        scheduler=probe,
        id="hourly-debt-reminder-job",
        trigger=IntervalTrigger(minutes=60),
        executor="default",
        func=jobs.run_debt_reminders,
        next_run_time=next_run_time,
        name="hourly debt reminders",
        args=(),
        kwargs={},
        misfire_grace_time=jobs.GRACE_PERIOD,
        coalesce=True,
        max_instances=3,
    )
    store.add_job(job)


def _registered_next_run(probe):
    """The time start() would hand to the executor for the seeded job."""
    for job, _store, _replace in probe._pending_jobs:
        if job.id == "hourly-debt-reminder-job":
            return getattr(job, "next_run_time", None)
    return None


def test_restart_keeps_a_run_that_came_due_while_the_app_was_down(monkeypatch):
    """A restart five minutes after the hour must not throw the run away.

    replace_existing recomputes next_run_time from now, so the stored time was
    silently replaced by the next occurrence and misfire_grace_time never came
    into play. The job looked scheduled and simply never fired.
    """
    probe, store = _stopped_scheduler(monkeypatch)
    owed = datetime.now(timezone.utc) - timedelta(minutes=5)
    _seed(probe, store, owed)

    jobs.start_report_schedulers()

    assert _registered_next_run(probe) == owed


def test_restart_drops_a_run_older_than_the_misfire_grace(monkeypatch):
    """A run left too late would fail anyway, so the trigger takes over."""
    probe, store = _stopped_scheduler(monkeypatch)
    _seed(probe, store, datetime.now(timezone.utc) - timedelta(hours=4))

    jobs.start_report_schedulers()

    assert _registered_next_run(probe) is None


def test_restart_keeps_a_run_that_is_not_due_yet(monkeypatch):
    """Recomputing from now pushed every future time a full period back.

    For the hourly job that reset its phase on every restart: restarting more
    often than once an hour meant it never fired at all.
    """
    probe, store = _stopped_scheduler(monkeypatch)
    soon = datetime.now(timezone.utc) + timedelta(minutes=10)
    _seed(probe, store, soon)

    jobs.start_report_schedulers()

    assert _registered_next_run(probe) == soon


def test_misfire_grace_matches_the_scheduler_default():
    """The two must agree or a carried run expires under a different rule."""
    from src.tasks.scheduler import job_defaults

    assert jobs.GRACE_PERIOD == job_defaults["misfire_grace_time"]
