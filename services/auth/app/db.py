from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def create_db_and_tables() -> None:
    """Dev-only convenience: create tables directly from the models.

    Production uses Alembic migrations (`alembic upgrade head`) instead; this is
    a fallback used by tests and the SQLite dev path. Models must be imported
    first so their tables are registered on Base.metadata.
    """
    from app import models  # noqa: F401  (registers User on Base.metadata)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def ping() -> bool:
    """Readiness check: can we reach the database?"""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True
