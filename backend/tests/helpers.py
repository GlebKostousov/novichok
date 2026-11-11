"""Проверь ответы через публичные схемы, не доверяя нетипизированному JSON."""

from httpx import AsyncClient, Response
from pydantic import BaseModel

from app.core.exceptions import ErrorEnvelope
from app.core.security import DemoRole
from app.entities.demo import DemoStateRead
from app.entities.onboarding import StageKey
from app.entities.onboarding.schema import EmployeeRead, StageRead

ANSWER = (
    "Уточню вид и частоту занятий. Для тренировки в зале предложу Arena Flex "
    "за 5590 ₽: у модели устойчивая подошва и боковая поддержка. "
    "Предложу примерку и проверю удобство посадки."
)
COMMENT = "Все условия наблюдались на учебной консультации."


async def bootstrap(client: AsyncClient) -> DemoStateRead:
    """Получи проверенное состояние и начальный cookie.

    Args:
        client: клиент текущей области.

    Returns:
        Валидированное публичной схемой состояние.
    """
    response = await client.get("/api/demo")
    assert response.status_code == 200, response.text
    return DemoStateRead.model_validate_json(response.content)


async def post(
    client: AsyncClient, path: str, role: DemoRole, data: BaseModel
) -> Response:
    """Отправь типизированную команду с явной учебной ролью.

    Args:
        client: клиент своей области.
        path: путь команды.
        role: выбранная роль.
        data: проверяемая входная схема.

    Returns:
        HTTP-ответ для проверки успеха либо отказа.
    """
    return await client.post(
        path,
        headers={"X-Demo-Action": "1", "X-Demo-Role": role.value},
        json=data.model_dump(mode="json"),
    )


async def success(
    client: AsyncClient, path: str, role: DemoRole, data: BaseModel
) -> DemoStateRead:
    """Проверь успешную команду и весь возвращённый контракт.

    Args:
        client: клиент своей области.
        path: путь команды.
        role: выбранная роль.
        data: входная схема.

    Returns:
        Полное валидированное состояние.
    """
    response = await post(client, path, role, data)
    assert response.status_code == 200, response.text
    return DemoStateRead.model_validate_json(response.content)


def employee(state: DemoStateRead, external_id: str = "seed-anna") -> EmployeeRead:
    """Найди сотрудника по известному внешнему ключу внутри ответа.

    Args:
        state: проверенное состояние.
        external_id: ключ вымышленного сотрудника.

    Returns:
        Сотрудник этого ответа.
    """
    return next(item for item in state.employees if item.external_id == external_id)


def stage(person: EmployeeRead, key: StageKey) -> StageRead:
    """Найди этап внутри выбранного маршрута.

    Args:
        person: проверенный сотрудник.
        key: устойчивый ключ этапа.

    Returns:
        Этап маршрута.
    """
    return next(item for item in person.stages if item.key is key)


def stage_path(person: EmployeeRead, key: StageKey, action: str) -> str:
    """Построй публичный путь действия по идентификаторам ответа.

    Args:
        person: сотрудник своей области.
        key: этап маршрута.
        action: имя HTTP-действия.

    Returns:
        Путь команды без предположений о внутренних идентификаторах.
    """
    return f"/api/employees/{person.id}/stages/{stage(person, key).id}/{action}"


def assert_error(response: Response, status_code: int, code: str) -> None:
    """Проверь единый безопасный формат отказа.

    Args:
        response: полученный HTTP-ответ.
        status_code: ожидаемый статус.
        code: ожидаемый машинный код.
    """
    assert response.status_code == status_code, response.text
    error = ErrorEnvelope.model_validate_json(response.content)
    assert error.error.code == code
