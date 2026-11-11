"""Собери приложение, которому явно принадлежат ресурсы и HTTP-маршруты."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.clock import Clock, SystemClock
from app.core.config import Settings
from app.core.db import Database
from app.core.exceptions import register_error_handlers
from app.core.logging import configure_logging
from app.entities.onboarding import OnboardingCatalog
from app.web import demo, employees, health
from app.web.middleware import ApiBoundaryMiddleware
from app.web.runtime import Runtime
from app.web.static import register_static


def create_app(
    settings: Settings | None = None, *, clock: Clock | None = None
) -> FastAPI:
    """Собери независимый процесс без соединений на уровне импорта.

    Args:
        settings: явная тестовая конфигурация либо окружение процесса.
        clock: заменяемые часы либо системное время UTC.

    Returns:
        Настроенное приложение с владельцем ресурсов в lifespan.
    """
    config = settings or Settings()
    current_clock = clock or SystemClock()
    configure_logging(json_output=config.log_json)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Открой и гарантированно закрой движок одного процесса.

        Args:
            app: запущенное приложение.

        Yields:
            Время жизни готового приложения.
        """
        database = Database(config.database_url)
        try:
            await database.check_connection()
            app.state.runtime = Runtime(
                database, config, current_clock, OnboardingCatalog()
            )
            yield
        finally:
            await database.close()

    app = FastAPI(
        title="Новичок — демонстрация адаптации",
        version="0.1.0",
        description=(
            "Изолированные вымышленные данные; "
            "роли переключаются для проверки сценария."
        ),
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    register_error_handlers(app)
    app.add_middleware(ApiBoundaryMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.allowed_hosts)
    app.include_router(demo.router, prefix="/api")
    app.include_router(employees.router, prefix="/api")
    app.include_router(health.router, prefix="/api")
    if config.static_dir is not None:
        register_static(app, config.static_dir)
    return app
