"""Проверь повтор кадрового события, конфликты версий и конкурентные записи."""

import asyncio
from datetime import timedelta
from uuid import UUID

import pytest
from httpx import AsyncClient

from app.core.security import DemoRole
from app.entities.demo import DemoStateRead, HireCreate, LastEventRead
from app.entities.onboarding import StageKey
from app.entities.onboarding.schema import RevisionInput, SubmissionCreate
from app.workflows.demo._reader import DemoReader

from .helpers import (
    ANSWER,
    assert_error,
    bootstrap,
    employee,
    post,
    stage_path,
    success,
)


async def test_hire_replay_is_idempotent_before_revision_check(
    client: AsyncClient,
) -> None:
    """Верни прежний маршрут при точном повторе со старой версией.

    Args:
        client: клиент собственной области.
    """
    state = await bootstrap(client)
    command = HireCreate(
        expected_revision=state.revision,
        external_id="event-100",
        full_name="Сергей Учебный",
        department_id="north",
        start_date=state.today - timedelta(days=2),
    )
    created = await success(client, "/api/demo/hire", DemoRole.MANAGER, command)
    repeated = await success(client, "/api/demo/hire", DemoRole.MANAGER, command)
    assert repeated.revision == created.revision
    assert repeated.employees == created.employees
    assert repeated.activities == created.activities
    assert repeated.metrics.employees_total == 4
    assert repeated.last_event is not None
    assert repeated.last_event.outcome == "already_processed"
    conflict = command.model_copy(update={"department_id": "center"})
    response = await post(client, "/api/demo/hire", DemoRole.MANAGER, conflict)
    assert_error(response, 409, "event_conflict")
    assert (await bootstrap(client)) == created


async def test_stale_revision_does_not_overwrite_answer(client: AsyncClient) -> None:
    """Останови вторую вкладку, сохранив первый зафиксированный ответ.

    Args:
        client: клиент собственной области.
    """
    state = await bootstrap(client)
    path = stage_path(employee(state), StageKey.PRODUCT, "submit")
    command = SubmissionCreate(expected_revision=state.revision, text=ANSWER)
    saved = await success(client, path, DemoRole.EMPLOYEE, command)
    overwritten = await post(client, path, DemoRole.EMPLOYEE, command)
    assert_error(overwritten, 409, "stale_state")
    assert (await bootstrap(client)) == saved


async def test_concurrent_submission_has_single_winner(client: AsyncClient) -> None:
    """Проверь реальный конкурентный compare-and-swap на подключённой базе.

    Args:
        client: клиент собственной области.
    """
    state = await bootstrap(client)
    path = stage_path(employee(state), StageKey.PRODUCT, "submit")
    command = SubmissionCreate(expected_revision=state.revision, text=ANSWER)
    responses = await asyncio.gather(
        post(client, path, DemoRole.EMPLOYEE, command),
        post(client, path, DemoRole.EMPLOYEE, command),
    )
    assert sorted(item.status_code for item in responses) == [200, 409]
    failed = next(item for item in responses if item.status_code == 409)
    assert_error(failed, 409, "stale_state")
    refreshed = await bootstrap(client)
    assert refreshed.revision == state.revision + 1
    assert len(refreshed.activities) == len(state.activities) + 1


async def test_concurrent_same_hire_returns_one_route(client: AsyncClient) -> None:
    """Обработай одновременно доставленное событие без дубля сотрудника.

    Args:
        client: клиент собственной области.
    """
    state = await bootstrap(client)
    command = HireCreate(
        expected_revision=state.revision,
        external_id="simultaneous-100",
        full_name="Вера Учебная",
        department_id="center",
        start_date=state.today,
    )
    responses = await asyncio.gather(
        post(client, "/api/demo/hire", DemoRole.MANAGER, command),
        post(client, "/api/demo/hire", DemoRole.MANAGER, command),
    )
    assert [item.status_code for item in responses] == [200, 200]
    states = [DemoStateRead.model_validate_json(item.content) for item in responses]
    outcomes = {
        item.last_event.outcome for item in states if item.last_event is not None
    }
    assert outcomes == {"created", "already_processed"}
    current = await bootstrap(client)
    assert current.metrics.employees_total == 4
    assert current.revision == state.revision + 1


async def test_reset_during_hire_replay_cannot_claim_missing_route(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Отклони повтор, если конкурирующий сброс уже удалил его результат.

    Args:
        client: браузер своей области.
        monkeypatch: управление точным порядком двух настоящих HTTP-команд.
    """
    state = await bootstrap(client)
    command = HireCreate(
        expected_revision=state.revision,
        external_id="reset-race-100",
        full_name="Учебный Сотрудник",
        department_id="center",
        start_date=state.today,
    )
    created = await success(client, "/api/demo/hire", DemoRole.MANAGER, command)
    original_read = DemoReader.read

    async def read_after_reset(
        reader: DemoReader,
        workspace_id: UUID,
        *,
        last_event: LastEventRead | None = None,
    ) -> DemoStateRead:
        """Выполни сброс после lookup события, перед стабилизацией снимка.

        Args:
            reader: обычный сборщик ответа.
            workspace_id: проверенная область.
            last_event: результат, который собирается объявить повтор.

        Returns:
            Настоящий снимок после конкурирующего сброса.
        """
        if last_event is not None and last_event.outcome == "already_processed":
            await success(
                client,
                "/api/demo/reset",
                DemoRole.MANAGER,
                RevisionInput(expected_revision=created.revision),
            )
        return await original_read(reader, workspace_id, last_event=last_event)

    monkeypatch.setattr(DemoReader, "read", read_after_reset)
    response = await post(client, "/api/demo/hire", DemoRole.MANAGER, command)
    assert_error(response, 409, "stale_state")
    current = await bootstrap(client)
    assert current.metrics.employees_total == 3
    assert current.last_event is None
