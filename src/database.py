from functools import lru_cache
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.config import get_settings


DATABASE_URL = get_settings().DATABASE_URL

Base = declarative_base()

engine = create_async_engine(url=DATABASE_URL, echo=True, connect_args={"ssl":"require","statement_cache_size": 0})
get_async_session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with get_async_session_maker() as db:
        try:
            yield db
        finally:
            await db.close()
