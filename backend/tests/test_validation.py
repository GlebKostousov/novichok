"""Проверь границы входа, прав роли и критериев подтверждения."""

from datetime import timedelta

import pytest
from httpx import AsyncClient

from app.core.security import DemoRole
from app.entities.onboarding import ReviewDecision, StageKey
from app.entities.onboarding.schema import ReviewCreate, SubmissionCreate

from .helpers import ANSWER, assert_error, bootstrap, employee, post, stage_path


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("expected_revision", True),
        ("expected_revision", "1"),
        ("expected_revision", 1.5),
        ("expected_revision", 10**30),
        ("external_id", "../wrong"),
        ("external_id", "aa"),
        ("full_name", "Иван\x00Учебный"),
        ("full_name", "   "),
        ("department_id", "unknown"),
        ("start_date", "2026-11-11T00:00:00Z"),
        ("start_date", 1_794_355_200),
        ("surprise_field", "unsupported"),
    ],
)
async def test_hire_rejects_invalid_fields_without_mutation(
    client: AsyncClient, field: str, value: object
) -> None:
    """Проверь типы, неизвестные поля, управляющие символы и подразделения.

    Args:
        client: клиент текущей области.
        field: атакуемое поле запроса.
        value: намеренно некорректное значение.
    """
    state = await bootstrap(client)
    body: dict[str, object] = {
        "expected_revision": state.revision,
        "external_id": "validation-1",
        "full_name": "Учебный Сотрудник",
        "department_id": "center",
        "start_date": state.today.isoformat(),
    }
    body[field] = value
    response = await client.post(
        "/api/demo/hire",
        headers={"X-Demo-Action": "1", "X-Demo-Role": "manager"},
        json=body,
    )
    assert_error(response, 422, "validation_error")
    assert (await bootstrap(client)) == state


@pytest.mark.parametrize("offset", [-366, 1])
async def test_hire_rejects_out_of_range_actual_start(
    client: AsyncClient, offset: int
) -> None:
    """Не выдавай будущий план выхода за фактическое кадровое событие.

    Args:
        client: клиент текущей области.
        offset: выход за допустимые границы даты.
    """
    state = await bootstrap(client)
    response = await client.post(
        "/api/demo/hire",
        headers={"X-Demo-Action": "1", "X-Demo-Role": "manager"},
        json={
            "expected_revision": state.revision,
            "external_id": "date-boundary",
            "full_name": "Учебный Сотрудник",
            "department_id": "center",
            "start_date": (state.today + timedelta(days=offset)).isoformat(),
        },
    )
    assert_error(response, 422, "validation_error")
    assert (await bootstrap(client)) == state


@pytest.mark.parametrize(
    "criteria", [[], ["needs"], ["needs", "facts", "next_step", "needs"], ["unknown"]]
)
async def test_approval_requires_exact_known_criteria(
    client: AsyncClient, criteria: list[str]
) -> None:
    """Не принимай неполное подтверждение, дубли и чужие критерии.

    Args:
        client: клиент текущей области.
        criteria: намеренно некорректное множество критериев.
    """
    state = await bootstrap(client)
    person = employee(state, "seed-dmitry")
    response = await post(
        client,
        stage_path(person, StageKey.PRODUCT, "review"),
        DemoRole.MENTOR,
        ReviewCreate(
            expected_revision=state.revision,
            decision=ReviewDecision.APPROVED,
            comment="Проверка по всем наблюдаемым критериям.",
            checked_criteria=criteria,
        ),
    )
    assert_error(response, 422, "invalid_criteria")
    assert (await bootstrap(client)) == state


async def test_return_requires_substantive_comment(client: AsyncClient) -> None:
    """Не возвращай сотруднику задание без понятного замечания.

    Args:
        client: клиент текущей области.
    """
    state = await bootstrap(client)
    response = await post(
        client,
        stage_path(employee(state, "seed-dmitry"), StageKey.PRODUCT, "review"),
        DemoRole.MENTOR,
        ReviewCreate(
            expected_revision=state.revision,
            decision=ReviewDecision.CHANGES_REQUESTED,
            comment="Исправь",
            checked_criteria=[],
        ),
    )
    assert_error(response, 422, "validation_error")
    assert (await bootstrap(client)) == state


async def test_role_and_action_header_are_required(client: AsyncClient) -> None:
    """Отклони скрытый вызов без action-заголовка и действие чужой роли.

    Args:
        client: клиент текущей области.
    """
    state = await bootstrap(client)
    path = stage_path(employee(state), StageKey.PRODUCT, "submit")
    body = SubmissionCreate(expected_revision=state.revision, text=ANSWER)
    missing_header = await client.post(path, json=body.model_dump())
    assert_error(missing_header, 403, "demo_action_required")
    missing_role = await client.post(
        path, headers={"X-Demo-Action": "1"}, json=body.model_dump()
    )
    assert_error(missing_role, 403, "role_forbidden")
    wrong_role = await post(client, path, DemoRole.MANAGER, body)
    assert_error(wrong_role, 403, "role_forbidden")
    assert (await bootstrap(client)) == state


@pytest.mark.parametrize("action", ["submit", "review"])
async def test_null_character_is_rejected_before_database_write(
    client: AsyncClient, action: str
) -> None:
    """Не передавай запрещённый PostgreSQL NUL в текст ответа или решения.

    Args:
        client: клиент текущей области.
        action: проверяемая текстовая команда.
    """
    state = await bootstrap(client)
    commands: dict[str, tuple[str, str, dict[str, object]]] = {
        "submit": (
            "seed-anna",
            "employee",
            {"text": ANSWER + "\x00"},
        ),
        "review": (
            "seed-dmitry",
            "mentor",
            {
                "decision": "changes_requested",
                "comment": "Поясните следующий шаг\x00",
                "checked_criteria": [],
            },
        ),
    }
    external_id, role, body = commands[action]
    body["expected_revision"] = state.revision
    response = await client.post(
        stage_path(employee(state, external_id), StageKey.PRODUCT, action),
        headers={"X-Demo-Action": "1", "X-Demo-Role": role},
        json=body,
    )
    assert_error(response, 422, "validation_error")
    assert (await bootstrap(client)) == state
