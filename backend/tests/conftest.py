"""Подготовь реальные миграции и независимое приложение для каждого сценария."""

import asyncio
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.engine import make_url

from app.app_factory import create_app
from app.core.config import Settings
from app.core.db import Database
from app.entities.demo import DemoWorkspace

BACKEND_ROOT = Path(__file__).resolve().parents[1]


@dataclass(slots=True)
class FrozenClock:
    """Сделай даты тестов воспроизводимыми и разреши явную проверку истечения.

    Attributes:
        value: текущий момент тестового сценария.
    """

    value: datetime

    def now(self) -> datetime:
        """Верни момент, заданный самим тестом."""
        return self.value


@pytest.fixture
def clock() -> FrozenClock:
    """Верни независимые часы UTC для одного теста."""
    return FrozenClock(datetime(2026, 11, 11, 12, 0, tzinfo=UTC))


def migration_config(url: str) -> Config:
    """Настрой миграции на явно выделенную тестом базу.

    Args:
        url: URL временной SQLite либо отдельной PostgreSQL test-базы.

    Returns:
        Конфигурация Alembic без изменения рабочего окружения.
    """
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def _select_database(tmp_path: Path) -> str:
    """Разреши внешнюю БД только при явном имени с суффиксом _test.

    Args:
        tmp_path: индивидуальный каталог временного SQLite-файла.

    Returns:
        Строка подключения выделенной тестовой базы.
    """
    configured = os.environ.get("TEST_DATABASE_URL")
    if configured is None:
        return f"sqlite+aiosqlite:///{tmp_path / 'demo.sqlite3'}"
    database = make_url(configured).database or ""
    if not database.endswith("_test"):
        message = "TEST_DATABASE_URL должен указывать отдельную базу с суффиксом _test"
        raise RuntimeError(message)
    return configured


@pytest.fixture
async def database_url(tmp_path: Path) -> str:
    """Примени настоящую миграцию и очисти только выделенную тестовую базу.

    Args:
        tmp_path: временный каталог теста.

    Returns:
        Подготовленный URL.
    """
    url = _select_database(tmp_path)
    await asyncio.to_thread(command.upgrade, migration_config(url), "head")
    database = Database(url)
    try:
        async with database.engine.begin() as connection:
            await connection.execute(delete(DemoWorkspace))
    finally:
        await database.close()
    return url


@pytest.fixture
def settings(database_url: str) -> Settings:
    """Собери явные настройки, независимые от .env и публичной демо-базы.

    Args:
        database_url: подготовленная выделенная база.

    Returns:
        Настройки одного тестового приложения.
    """
    return Settings(
        _env_file=None,
        database_url=database_url,
        cookie_secure=False,
        static_dir=None,
        allowed_hosts=["testserver"],
        max_workspaces=1000,
        log_json=False,
    )


@pytest.fixture
async def app(settings: Settings, clock: FrozenClock) -> AsyncIterator[FastAPI]:
    """Запусти и закрой приложение тем же lifespan, что используется сервером.

    Args:
        settings: явные настройки теста.
        clock: воспроизводимое время.

    Yields:
        Запущенное приложение с настоящими репозиториями.
    """
    application = create_app(settings, clock=clock)
    async with LifespanManager(application):
        yield application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Открой браузероподобный HTTP-клиент с собственными cookie.

    Args:
        app: запущенное тестовое приложение.

    Yields:
        Клиент без заранее заданной роли или чужих cookie.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as http_client:
        yield http_client
