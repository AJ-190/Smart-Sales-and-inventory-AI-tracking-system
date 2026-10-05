from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from src.config import get_settings


DATABASE_URL = get_settings().DATABASE_URL


class Base(DeclarativeBase):
    pass

engine = create_async_engine(
    url=DATABASE_URL,
    echo=False,
    connect_args={"ssl": "require", "statement_cache_size": 0},
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=300,
)
get_async_session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


# Scheduled jobs run via asyncio.run(), which builds a fresh event loop per
# invocation. Pooled asyncpg connections belong to the loop that opened them, so
# handing one to a job's loop raises "got Future attached to a different loop".
# NullPool opens and closes inside the job's own loop, so nothing is shared.
job_engine = create_async_engine(
    url=DATABASE_URL,
    echo=False,
    connect_args={"ssl": "require", "statement_cache_size": 0},
    poolclass=NullPool,
)
job_session_maker = async_sessionmaker(bind=job_engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with get_async_session_maker() as db:
        try:
            yield db
        finally:
            await db.close()
