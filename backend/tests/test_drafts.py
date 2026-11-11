"""Проверь серверные черновики отдельно от версии рабочего процесса."""

import asyncio

import pytest
from httpx import AsyncClient

from .helpers import assert_error, bootstrap, employee

HEADERS = {"X-Demo-Action": "1", "X-Demo-Role": "employee"}


async def test_draft_survives_read_without_changing_workflow(
    client: AsyncClient,
) -> None:
    """Сохрани ввод и не создавай действие либо новую версию маршрута."""
    state = await bootstrap(client)
    person = employee(state)
    key = f"{person.id}:{person.stages[1].id}:employee"
    response = await client.post(
        f"/api/demo/drafts/{key}",
        headers=HEADERS,
        json={"expected_version": 0, "fields": {"answer": "Мой незаконченный ответ"}},
    )
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["version"] == 1
    drafts = await client.get("/api/demo/drafts", headers=HEADERS)
    assert drafts.json() == [saved]
    assert await bootstrap(client) == state
    stale = await client.post(
        f"/api/demo/drafts/{key}",
        headers=HEADERS,
        json={"expected_version": 0, "fields": {"answer": "Другое окно"}},
    )
    assert_error(stale, 409, "draft_conflict")
    assert (await client.get("/api/demo/drafts", headers=HEADERS)).json() == [saved]


async def test_draft_rejects_foreign_employee_and_role(client: AsyncClient) -> None:
    """Не принимай чужие ключи и запись за другую учебную роль."""
    state = await bootstrap(client)
    person = employee(state)
    body = {"expected_version": 0, "fields": {"comment": "Черновик"}}
    key = f"{person.id}:{person.stages[1].id}:mentor"
    denied = await client.post(f"/api/demo/drafts/{key}", headers=HEADERS, json=body)
    assert_error(denied, 403, "role_forbidden")
    client.cookies.clear()
    await bootstrap(client)
    foreign = await client.post(
        f"/api/demo/drafts/{key}",
        headers={**HEADERS, "X-Demo-Role": "mentor"},
        json=body,
    )
    assert_error(foreign, 404, "not_found")
    assert (await client.get("/api/demo/drafts", headers=HEADERS)).json() == []


async def test_hire_draft_reset_and_bounded_fields(client: AsyncClient) -> None:
    """Сбрось черновики своей области и ограничь размер вводимого текста."""
    state = await bootstrap(client)
    headers = {**HEADERS, "X-Demo-Role": "manager"}
    path = "/api/demo/drafts/hire:manager"
    saved = await client.post(
        path,
        headers=headers,
        json={
            "expected_version": 0,
            "fields": {"full_name": "Новый Сотрудник"},
        },
    )
    assert saved.status_code == 200, saved.text
    invalid = await client.post(
        path,
        headers=headers,
        json={
            "expected_version": 1,
            "fields": {"answer": "x" * 2001},
        },
    )
    assert invalid.status_code == 422
    reset = await client.post(
        "/api/demo/reset", headers=headers, json={"expected_revision": state.revision}
    )
    assert reset.status_code == 200
    assert (await client.get("/api/demo/drafts", headers=headers)).json() == []


async def test_drafts_require_session_and_role(client: AsyncClient) -> None:
    """Не выдавай ввод без проверенного cookie и учебной роли."""
    assert_error(
        await client.get("/api/demo/drafts", headers=HEADERS), 401, "session_required"
    )
    await bootstrap(client)
    assert_error(await client.get("/api/demo/drafts"), 403, "role_forbidden")
    assert_error(
        await client.post(
            "/api/demo/drafts/hire:manager",
            json={
                "expected_version": 0,
                "fields": {},
            },
        ),
        403,
        "demo_action_required",
    )


async def test_concurrent_first_save_and_reset_do_not_reuse_version(
    client: AsyncClient,
) -> None:
    """Две первые записи дают 200/409, сброс не повторяет старую версию."""
    state = await bootstrap(client)
    headers = {**HEADERS, "X-Demo-Role": "manager"}
    path = "/api/demo/drafts/hire:manager"
    body = {"expected_version": 0, "fields": {"full_name": "Черновик"}}
    responses = await asyncio.gather(
        *[client.post(path, headers=headers, json=body) for _ in range(2)]
    )
    assert sorted(item.status_code for item in responses) == [200, 409]
    old = next(item.json() for item in responses if item.status_code == 200)
    await client.post(
        "/api/demo/reset", headers=headers, json={"expected_revision": state.revision}
    )
    created = await client.post(path, headers=headers, json=body)
    assert created.json()["version"] > old["version"]
    stale = await client.post(
        path,
        headers=headers,
        json={
            **body,
            "expected_version": old["version"],
        },
    )
    assert_error(stale, 409, "draft_conflict")


@pytest.mark.parametrize("version", [True, "0", -1, 2**31])
async def test_draft_version_is_strict(client: AsyncClient, version: object) -> None:
    """Отклони преобразуемые и выходящие за границы версии."""
    await bootstrap(client)
    response = await client.post(
        "/api/demo/drafts/hire:manager",
        headers={**HEADERS, "X-Demo-Role": "manager"},
        json={"expected_version": version, "fields": {}},
    )
    assert response.status_code == 422
