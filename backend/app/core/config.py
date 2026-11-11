"""Прочитай настройки процесса из окружения без глобальных ресурсов."""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Опиши подключение, cookie и каталог собранного интерфейса."""

    model_config = SettingsConfigDict(
        env_prefix="NOVICHOK_", env_file=".env", extra="ignore"
    )

    database_url: str = Field(default="sqlite+aiosqlite:///./novichok.db", repr=False)
    cookie_secure: bool = False
    static_dir: Path | None = None
    allowed_hosts: list[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "testserver"]
    )
    max_workspaces: int = Field(default=1000, ge=1, le=100_000)
    log_json: bool = True

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        """Выбери явный асинхронный драйвер для поддерживаемой базы.

        Args:
            value: строка подключения из окружения.

        Returns:
            Строка подключения SQLAlchemy.
        """
        replacements = {
            "postgres://": "postgresql+asyncpg://",
            "postgresql://": "postgresql+asyncpg://",
            "sqlite:///": "sqlite+aiosqlite:///",
        }
        for prefix, replacement in replacements.items():
            if value.startswith(prefix):
                return replacement + value.removeprefix(prefix)
        return cls._validate_driver(value)

    @staticmethod
    def _validate_driver(value: str) -> str:
        """Отклони неподдерживаемый драйвер до запуска приложения.

        Args:
            value: строка подключения.

        Returns:
            Проверенная строка.
        """
        if not value.startswith(("sqlite+aiosqlite:///", "postgresql+asyncpg://")):
            message = "Используйте SQLite с aiosqlite либо PostgreSQL с asyncpg"
            raise ValueError(message)
        return value
