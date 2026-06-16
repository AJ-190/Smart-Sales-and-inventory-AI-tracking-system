from functools import lru_cache
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.config import get_settings


SYNC_DATABASE_URL = get_settings().DATABASE_URL
ASYNC_DATABASE_URL = SYNC_DATABASE_URL
if ASYNC_DATABASE_URL.startswith("postgresql://"):
    ASYNC_DATABASE_URL = ASYNC_DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_engine(SYNC_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


@lru_cache
def get_async_engine():
    return create_async_engine(ASYNC_DATABASE_URL)


@lru_cache
def get_async_session_maker():
    return async_sessionmaker(get_async_engine(), expire_on_commit=False)


async def get_db():
    async with get_async_session_maker() as db:
        try:
            yield db
        finally:
            await db.close()
