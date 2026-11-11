"""Предоставь тонкие HTTP-команды для изолированной демонстрационной области."""

from fastapi import APIRouter, Request, Response

from app.entities.demo.drafts import DraftRead, DraftWrite
from app.entities.demo.schema import DemoStateRead, HireCreate
from app.entities.onboarding.schema import RevisionInput
from app.web.dependencies import RuntimeDep, UowDep
from app.workflows.demo import COOKIE_NAME, SESSION_MAX_AGE_SECONDS, DraftWorkflow

from ._deps import ActorDep, DemoContextDep, DemoServiceDep

router = APIRouter(prefix="/demo", tags=["Демонстрация"])


@router.get("/drafts")
async def drafts(actor: ActorDep, uow: UowDep) -> list[DraftRead]:
    """Прочитай сохранённый ввод только своей демосессии."""
    return await DraftWorkflow(uow).read(actor)


@router.post("/drafts/{key}")
async def save_draft(
    key: str, data: DraftWrite, actor: ActorDep, uow: UowDep
) -> DraftRead:
    """Сохрани форму с отдельной проверкой версии черновика."""
    return await DraftWorkflow(uow).save(actor, key, data)


@router.get("")
async def bootstrap(
    request: Request, response: Response, service: DemoServiceDep, runtime: RuntimeDep
) -> DemoStateRead:
    """Верни существующую область либо создай отдельную копию синтетики.

    Args:
        request: запрос с необязательным cookie.
        response: ответ для установки HttpOnly cookie.
        service: сценарий демосессии.
        runtime: настройки cookie.

    Returns:
        Полное состояние без токена сессии.
    """
    result = await service.bootstrap(request.cookies.get(COOKIE_NAME))
    if result.new_token is not None:
        response.set_cookie(
            COOKIE_NAME,
            result.new_token,
            max_age=SESSION_MAX_AGE_SECONDS,
            httponly=True,
            secure=runtime.settings.cookie_secure,
            samesite="lax",
            path="/",
        )
    return result.state


@router.post("/reset")
async def reset(data: RevisionInput, context: DemoContextDep) -> DemoStateRead:
    """Сбрось только текущую демонстрационную область.

    Args:
        data: версия клиента.
        context: сервисы и проверенный актор.

    Returns:
        Исходные данные с увеличенной версией.
    """
    return await context.service.reset(context.actor, data)


@router.post("/hire")
async def hire(data: HireCreate, context: DemoContextDep) -> DemoStateRead:
    """Имитируй нормализованное событие фактического выхода.

    Args:
        data: версия и проверенные кадровые поля.
        context: сценарий найма и проверенный актор.

    Returns:
        Новый либо уже существующий маршрут.
    """
    return await context.hire.hire(context.actor, data)
