"""Проверь cookie, предел тела, CORS, статику и безопасную готовность БД."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import SQLAlchemyError

from app.app_factory import create_app
from app.core.config import Settings
from app.entities.demo import DemoStateRead
from app.web.runtime import Runtime
from app.workflows.demo import COOKIE_NAME

from .conftest import FrozenClock
from .helpers import assert_error, bootstrap


async def test_cookie_is_private_and_state_is_not_cached(client: AsyncClient) -> None:
    """Не выдавай токен в JSON и не кешируй персональную область.

    Args:
        client: браузер собственной области.
    """
    response = await client.get("/api/demo")
    state = DemoStateRead.model_validate_json(response.content)
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Max-Age=604800" in cookie
    assert client.cookies[COOKIE_NAME] not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert state.metrics.employees_total == 3
    assert state.metrics.overdue_stages == 1
    assert state.metrics.completed_stages == 4
    assert state.metrics.awaiting_review == 1


async def _oversized_chunks() -> AsyncIterator[bytes]:
    """Отправь тело без Content-Length несколькими порциями."""
    yield b'{"text":"'
    yield b"x" * (17 * 1024)
    yield b'"}'


async def test_chunked_body_cannot_bypass_size_limit(client: AsyncClient) -> None:
    """Проверь фактические байты, даже если размер не объявлен заголовком.

    Args:
        client: браузер собственной области.
    """
    state = await bootstrap(client)
    response = await client.post(
        "/api/demo/reset",
        headers={
            "X-Demo-Action": "1",
            "X-Demo-Role": "manager",
            "Content-Type": "application/json",
        },
        content=_oversized_chunks(),
    )
    assert_error(response, 413, "body_too_large")
    assert (await bootstrap(client)) == state


async def test_foreign_site_gets_no_cors_permission(client: AsyncClient) -> None:
    """Не разрешай браузеру другого сайта отправлять команды с cookie.

    Args:
        client: HTTP-клиент без особых CORS-привилегий.
    """
    response = await client.options(
        "/api/demo/hire",
        headers={
            "Origin": "https://unrelated.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-demo-action,x-demo-role",
        },
    )
    assert "access-control-allow-origin" not in response.headers
    assert response.status_code == 405


async def test_health_hides_database_details(
    client: AsyncClient, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ответь 503 без текста драйвера при недоступном хранилище.

    Args:
        client: HTTP-клиент.
        app: запущенное приложение.
        monkeypatch: ограниченная подмена отказа соединения.
    """
    healthy = await client.get("/api/health")
    assert healthy.status_code == 200

    async def fail_connection() -> None:
        """Сымитируй диагностический текст, запрещённый в публичном ответе."""
        message = "database_secret_connection_details"
        raise SQLAlchemyError(message)

    runtime = cast(Runtime, app.state.runtime)
    monkeypatch.setattr(runtime.database, "check_connection", fail_connection)
    response = await client.get("/api/health")
    assert_error(response, 503, "database_unavailable")
    assert "database_secret_connection_details" not in response.text


async def test_static_fallback_preserves_api_404_and_blocks_path_escape(
    settings: Settings, clock: FrozenClock, tmp_path: Path
) -> None:
    """Раздай SPA-маршрут, сохранив границу API и статического каталога.

    Args:
        settings: явная тестовая конфигурация.
        clock: воспроизводимое время.
        tmp_path: временный каталог тестовых файлов.
    """
    directory = tmp_path / "static"
    directory.mkdir()
    (directory / "index.html").write_text(
        "<h1>Учебный интерфейс</h1>", encoding="utf-8"
    )
    (directory / "demo.webm").write_bytes(b"video-fixture")
    app = create_app(settings.model_copy(update={"static_dir": directory}), clock=clock)
    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            page = await client.get("/employees/example")
            assert page.status_code == 200
            assert "Учебный интерфейс" in page.text
            missing_api = await client.get("/api/unknown")
            assert_error(missing_api, 404, "http_error")
            missing_asset = await client.get("/missing.js")
            assert_error(missing_asset, 404, "http_error")
            video = await client.head("/demo.webm")
            assert video.status_code == 200
            assert video.headers["content-type"] == "video/webm"
            assert video.content == b""
            assert video.headers["content-length"] == "13"
            missing_video = await client.head("/missing.webm")
            assert missing_video.status_code == 404


async def test_static_blocks_symlink_escape(
    settings: Settings, clock: FrozenClock, tmp_path: Path
) -> None:
    """Проверь symlink отдельно; без привилегии пропусти только этот случай."""
    directory = tmp_path / "static"
    directory.mkdir()
    (directory / "index.html").write_text("index", encoding="utf-8")
    outside = tmp_path / "private.txt"
    outside.write_text("outside-secret", encoding="utf-8")
    try:
        (directory / "escape.txt").symlink_to(outside)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("Windows не предоставил привилегию создания symlink")
        raise
    app = create_app(settings.model_copy(update={"static_dir": directory}), clock=clock)
    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            escaping = await client.get("/escape.txt")
            assert_error(escaping, 404, "http_error")
            assert "outside-secret" not in escaping.text
