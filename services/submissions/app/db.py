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
    """Dev/test fallback; production uses Alembic (see migrations/).

    create_all only creates missing TABLES — it never alters existing ones —
    so for the throwaway SQLite path we also add any columns that were
    introduced after the local file was created (e.g. user_email, added in
    migration 0002). Postgres deployments get this via `alembic upgrade head`.
    """
    from sqlalchemy import inspect, text

    from app import models  # noqa: F401

    def _sync_schema(sync_conn) -> None:
        Base.metadata.create_all(sync_conn)
        inspector = inspect(sync_conn)
        for table in Base.metadata.sorted_tables:
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name not in existing:
                    ddl = f'ALTER TABLE "{table.name}" ADD COLUMN {column.name} ' + str(
                        column.type.compile(sync_conn.dialect)
                    )
                    sync_conn.execute(text(ddl))

    async with engine.begin() as conn:
        await conn.run_sync(_sync_schema)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def ping() -> bool:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True
