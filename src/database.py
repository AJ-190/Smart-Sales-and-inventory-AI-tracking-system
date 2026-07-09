from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.config import get_settings


DATABASE_URL = get_settings().DATABASE_URL
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    separator = "&" if "?" in DATABASE_URL else "?"
    DATABASE_URL += f"{separator}statement_cache_size=0"

Base = declarative_base()

engine = create_async_engine(
    url=DATABASE_URL,
    echo=False,
    connect_args={"ssl": "require"},
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
get_async_session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with get_async_session_maker() as db:
        try:
            yield db
        finally:
            await db.close()
