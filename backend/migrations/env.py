"""Выполни миграции одинаково для асинхронных SQLite и PostgreSQL."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings
from app.entities.demo import DemoWorkspace
from app.entities.onboarding import Employee

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = DemoWorkspace.metadata
if Employee.metadata is not target_metadata:
    message = "Все предметные таблицы должны использовать общую metadata"
    raise RuntimeError(message)


def database_url() -> str:
    """Используй явный URL тестов либо проверенное окружение процесса."""
    return config.get_main_option("sqlalchemy.url") or Settings().database_url


def run_migrations_offline() -> None:
    """Сгенерируй SQL без открытия соединения."""
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_sync_migrations(connection: Connection) -> None:
    """Выполни ревизии через синхронную грань асинхронного соединения.

    Args:
        connection: соединение, принадлежащее запуску миграций.
    """
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Открой одно соединение и закрой его даже при ошибке миграции."""
    engine = create_async_engine(database_url(), poolclass=pool.NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(run_sync_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
