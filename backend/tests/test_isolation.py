"""Проверь непрозрачные cookie, чужие идентификаторы и истечение области."""

from datetime import timedelta

from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.app_factory import create_app
from app.core.config import Settings
from app.core.security import DemoRole
from app.entities.onboarding import StageKey
from app.entities.onboarding.schema import RevisionInput, SubmissionCreate
from app.workflows.demo import COOKIE_NAME

from .conftest import FrozenClock
from .helpers import (
    ANSWER,
    assert_error,
    bootstrap,
    employee,
    post,
    stage_path,
    success,
)


async def test_foreign_employee_and_foreign_stage_are_not_found(
    client: AsyncClient, app: FastAPI
) -> None:
    """Не разрешай угадывание UUID между областями и маршрутами.

    Args:
        client: первый браузер.
        app: запущенное приложение для второго браузера.
    """
    first = await bootstrap(client)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as other:
        second = await bootstrap(other)
        assert {item.id for item in first.employees}.isdisjoint(
            item.id for item in second.employees
        )
        foreign = await post(
            other,
            stage_path(employee(first), StageKey.PRODUCT, "submit"),
            DemoRole.EMPLOYEE,
            SubmissionCreate(expected_revision=second.revision, text=ANSWER),
        )
        assert_error(foreign, 404, "not_found")
        assert (await bootstrap(other)) == second
    own = employee(first)
    another = employee(first, "seed-dmitry")
    mixed_path = stage_path(another, StageKey.PRODUCT, "submit").replace(
        str(another.id), str(own.id)
    )
    mixed = await post(
        client,
        mixed_path,
        DemoRole.EMPLOYEE,
        SubmissionCreate(expected_revision=first.revision, text=ANSWER),
    )
    assert_error(mixed, 404, "not_found")
    assert (await bootstrap(client)) == first


async def test_reset_does_not_modify_another_browser(
    client: AsyncClient, app: FastAPI
) -> None:
    """Замени данными только область предъявленного cookie.

    Args:
        client: первый браузер.
        app: приложение для второго браузера.
    """
    first = await bootstrap(client)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as other:
        second = await bootstrap(other)
        reset = await success(
            client,
            "/api/demo/reset",
            DemoRole.EMPLOYEE,
            RevisionInput(expected_revision=first.revision),
        )
        assert reset.revision == first.revision + 1
        assert {item.id for item in reset.employees}.isdisjoint(
            item.id for item in first.employees
        )
        assert reset.metrics == first.metrics
        assert (await bootstrap(other)) == second


async def test_expired_and_forged_cookie_cannot_mutate_state(
    client: AsyncClient, clock: FrozenClock
) -> None:
    """Откажи старому cookie и выдай новую область только через bootstrap.

    Args:
        client: браузер текущей области.
        clock: управляемые часы приложения.
    """
    first = await bootstrap(client)
    clock.value += timedelta(days=8)
    expired = await post(
        client,
        "/api/demo/reset",
        DemoRole.MANAGER,
        RevisionInput(expected_revision=first.revision),
    )
    assert_error(expired, 401, "session_required")
    replacement = await bootstrap(client)
    assert {item.id for item in first.employees}.isdisjoint(
        item.id for item in replacement.employees
    )
    client.cookies.clear()
    client.cookies.set(COOKIE_NAME, "x" * 43)
    forged = await post(
        client, "/api/demo/reset", DemoRole.MANAGER, RevisionInput(expected_revision=1)
    )
    assert_error(forged, 401, "session_required")
    fresh = await bootstrap(client)
    assert fresh.revision == 1


async def test_state_survives_new_application_instance(
    client: AsyncClient, settings: Settings, clock: FrozenClock
) -> None:
    """Прочитай сохранённый результат через новый движок и процессный контекст.

    Args:
        client: исходный браузер.
        settings: то же внешнее хранилище.
        clock: воспроизводимые часы.
    """
    state = await bootstrap(client)
    saved = await success(
        client,
        stage_path(employee(state), StageKey.PRODUCT, "submit"),
        DemoRole.EMPLOYEE,
        SubmissionCreate(expected_revision=state.revision, text=ANSWER),
    )
    replacement = create_app(settings, clock=clock)
    async with LifespanManager(replacement):
        async with AsyncClient(
            transport=ASGITransport(app=replacement),
            base_url="http://testserver",
            cookies={COOKIE_NAME: client.cookies[COOKIE_NAME]},
        ) as resumed:
            assert (await bootstrap(resumed)) == saved
