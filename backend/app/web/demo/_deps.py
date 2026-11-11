"""Собери сервис демосессии и явного актора из cookie и учебной роли."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request

from app.core.security import DemoActor, DemoRole
from app.entities.onboarding.exceptions import RoleForbiddenError
from app.web.dependencies import RuntimeDep, UowDep
from app.workflows.demo import COOKIE_NAME, DemoService, HireWorkflow


def get_demo_service(uow: UowDep, runtime: RuntimeDep) -> DemoService:
    """Собери сценарии сессии в пределах текущей транзакции.

    Args:
        uow: единица работы запроса.
        runtime: ресурсы приложения.

    Returns:
        Сервис учебной области.
    """
    return DemoService(
        uow,
        catalog=runtime.catalog,
        clock=runtime.clock,
        max_workspaces=runtime.settings.max_workspaces,
    )


DemoServiceDep = Annotated[DemoService, Depends(get_demo_service)]


async def get_actor(
    request: Request,
    service: DemoServiceDep,
    role: Annotated[str | None, Header(alias="X-Demo-Role")] = None,
) -> DemoActor:
    """Свяжи выбранную учебную роль только с областью собственного cookie.

    Args:
        request: текущий запрос с непрозрачным cookie.
        service: сервис разрешения демосессии.
        role: выбранная посетителем роль, не подтверждение личности.

    Returns:
        Проверенная область и допустимая учебная роль.

    Raises:
        RoleForbiddenError: роль отсутствует либо неизвестна.
    """
    workspace_id = await service.workspace_id(request.cookies.get(COOKIE_NAME))
    if role is None:
        raise RoleForbiddenError()
    try:
        selected_role = DemoRole(role)
    except ValueError as error:
        raise RoleForbiddenError() from error
    return DemoActor(workspace_id, selected_role)


ActorDep = Annotated[DemoActor, Depends(get_actor)]


@dataclass(frozen=True, slots=True)
class DemoContext:
    """Передай роутерам явно собранные сервисы и актора.

    Attributes:
        service: сценарии сессии и сброса.
        hire: сценарий кадрового события.
        actor: проверенная область и выбранная роль.
    """

    service: DemoService
    hire: HireWorkflow
    actor: DemoActor


def get_demo_context(
    service: DemoServiceDep, actor: ActorDep, uow: UowDep, runtime: RuntimeDep
) -> DemoContext:
    """Собери контекст изменяющих demo-запросов.

    Args:
        service: сценарии сессии.
        actor: проверенный контекст посетителя.
        uow: общая транзакция.
        runtime: ресурсы приложения.

    Returns:
        Явный контекст маршрута HTTP.
    """
    return DemoContext(
        service,
        HireWorkflow(uow, catalog=runtime.catalog, clock=runtime.clock),
        actor,
    )


DemoContextDep = Annotated[DemoContext, Depends(get_demo_context)]
