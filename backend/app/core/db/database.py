"""Управляй асинхронным движком и выдачей транзакций."""

from typing import Protocol

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .unit_of_work import UnitOfWork


class _Cursor(Protocol):
    """Опиши только нужные операции курсора SQLite."""

    def execute(self, statement: str) -> object:
        """Выполни фиксированную настройку соединения."""
        ...

    def close(self) -> None:
        """Освободи курсор."""
        ...


class _Connection(Protocol):
    """Опиши DBAPI-границу SQLite без зависимости от драйвера."""

    def cursor(self) -> _Cursor:
        """Создай курсор соединения."""
        ...


def _configure_sqlite(connection: _Connection, record: object) -> None:
    """Включи внешние ключи и ограниченное ожидание записи в SQLite.

    Args:
        connection: соединение DBAPI.
        record: служебная запись пула SQLAlchemy.
    """
    cursor = connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
    finally:
        cursor.close()


class Database:
    """Владей движком до завершения lifespan приложения."""

    def __init__(self, url: str) -> None:
        """Создай движок без открытия сетевого соединения.

        Args:
            url: проверенная строка подключения.
        """
        self.engine = create_async_engine(url, pool_pre_ping=True, hide_parameters=True)
        if url.startswith("sqlite"):
            event.listen(self.engine.sync_engine, "connect", _configure_sqlite)
        self._sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    def unit_of_work(self) -> UnitOfWork:
        """Открой новую независимую единицу работы."""
        return UnitOfWork(self._sessions())

    async def check_connection(self) -> None:
        """Проверь возможность чтения базы без изменения данных."""
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def close(self) -> None:
        """Закрой пул при завершении приложения."""
        await self.engine.dispose()
