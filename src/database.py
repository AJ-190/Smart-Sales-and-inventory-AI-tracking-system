from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.config import get_settings


DATABASE_URL = get_settings().DATABASE_URL
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

Base = declarative_base()

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


async def get_db():
    async with get_async_session_maker() as db:
        try:
            yield db
        finally:
            await db.close()
