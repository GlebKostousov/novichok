"""Проверь ресурсные границы публичного демо и воспроизводимость схемы."""

import asyncio

from alembic import command
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from app.app_factory import create_app
from app.core.config import Settings
from app.core.security import DemoRole
from app.entities.demo import HireCreate

from .conftest import FrozenClock, migration_config
from .helpers import assert_error, bootstrap, post, success


async def test_employee_limit_keeps_twentieth_route_and_rejects_next(
    client: AsyncClient,
) -> None:
    """Ограничи область двадцатью сотрудниками без частично созданного маршрута.

    Args:
        client: клиент собственной области.
    """
    state = await bootstrap(client)
    for index in range(17):
        state = await success(
            client,
            "/api/demo/hire",
            DemoRole.MANAGER,
            HireCreate(
                expected_revision=state.revision,
                external_id=f"limit-{index}",
                full_name=f"Учебный Сотрудник {index}",
                department_id="center",
                start_date=state.today,
            ),
        )
    assert state.metrics.employees_total == 20
    response = await post(
        client,
        "/api/demo/hire",
        DemoRole.MANAGER,
        HireCreate(
            expected_revision=state.revision,
            external_id="over-limit",
            full_name="Лишний Сотрудник",
            department_id="center",
            start_date=state.today,
        ),
    )
    assert_error(response, 409, "demo_limit")
    assert (await bootstrap(client)) == state


async def test_workspace_limit_is_shared_between_application_instances(
    settings: Settings, clock: FrozenClock
) -> None:
    """Сохрани общий лимит даже при конкуренции двух экземпляров приложения.

    Args:
        settings: одна выделенная база.
        clock: воспроизводимое время.
    """
    limited = settings.model_copy(update={"max_workspaces": 1})
    first_app = create_app(limited, clock=clock)
    second_app = create_app(limited, clock=clock)
    async with LifespanManager(first_app), LifespanManager(second_app):
        async with (
            AsyncClient(
                transport=ASGITransport(app=first_app), base_url="http://testserver"
            ) as first,
            AsyncClient(
                transport=ASGITransport(app=second_app), base_url="http://testserver"
            ) as second,
        ):
            responses = await asyncio.gather(
                first.get("/api/demo"), second.get("/api/demo")
            )
            assert sorted(item.status_code for item in responses) == [200, 503]
            rejected = next(item for item in responses if item.status_code == 503)
            assert_error(rejected, 503, "demo_capacity")


async def test_migration_matches_models_and_can_rebuild(database_url: str) -> None:
    """Проверь upgrade, отсутствие дрейфа, downgrade и повторный upgrade.

    Args:
        database_url: исключительно выделенная тестовая база.
    """
    config = migration_config(database_url)
    await asyncio.to_thread(command.check, config)
    await asyncio.to_thread(command.downgrade, config, "base")
    await asyncio.to_thread(command.upgrade, config, "head")
    await asyncio.to_thread(command.check, config)
