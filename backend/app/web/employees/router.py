"""Предоставь тонкие HTTP-команды для проверяемых переходов маршрута."""

from uuid import UUID

from fastapi import APIRouter

from app.entities.demo.schema import DemoStateRead
from app.entities.onboarding.schema import (
    CommentInput,
    ObservationCreate,
    ReviewCreate,
    RevisionInput,
    SubmissionCreate,
)

from ._deps import EmployeesContextDep

router = APIRouter(prefix="/employees", tags=["Маршрут"])


@router.post("/{employee_id}/stages/{stage_id}/acknowledge")
async def acknowledge(
    employee_id: UUID, stage_id: UUID, data: RevisionInput, context: EmployeesContextDep
) -> DemoStateRead:
    """Подтверди ознакомление сотрудника с первым днём.

    Args:
        employee_id: сотрудник маршрута.
        stage_id: этап ознакомления.
        data: версия клиента.
        context: сервис и проверенный актор.

    Returns:
        Полное состояние после команды.
    """
    return await context.service.acknowledge(context.actor, employee_id, stage_id, data)


@router.post("/{employee_id}/stages/{stage_id}/submit")
async def submit(
    employee_id: UUID,
    stage_id: UUID,
    data: SubmissionCreate,
    context: EmployeesContextDep,
) -> DemoStateRead:
    """Отправь товарное задание наставнику.

    Args:
        employee_id: сотрудник маршрута.
        stage_id: товарное задание.
        data: версия и текст ответа.
        context: сервис и проверенный актор.

    Returns:
        Полное состояние после команды.
    """
    return await context.service.submit(context.actor, employee_id, stage_id, data)


@router.post("/{employee_id}/stages/{stage_id}/review")
async def review(
    employee_id: UUID, stage_id: UUID, data: ReviewCreate, context: EmployeesContextDep
) -> DemoStateRead:
    """Сохрани явное решение наставника по отправленной попытке.

    Args:
        employee_id: сотрудник маршрута.
        stage_id: товарное задание.
        data: версия, решение и критерии.
        context: сервис и проверенный актор.

    Returns:
        Полное состояние после команды.
    """
    return await context.service.review(context.actor, employee_id, stage_id, data)


@router.post("/{employee_id}/stages/{stage_id}/observe")
async def observe(
    employee_id: UUID,
    stage_id: UUID,
    data: ObservationCreate,
    context: EmployeesContextDep,
) -> DemoStateRead:
    """Подтверди наблюдаемую практику по всем критериям.

    Args:
        employee_id: сотрудник маршрута.
        stage_id: практический этап.
        data: версия, критерии и комментарий.
        context: сервис и проверенный актор.

    Returns:
        Полное состояние после команды.
    """
    return await context.service.observe(context.actor, employee_id, stage_id, data)


@router.post("/{employee_id}/stages/{stage_id}/approve")
async def approve(
    employee_id: UUID, stage_id: UUID, data: CommentInput, context: EmployeesContextDep
) -> DemoStateRead:
    """Сохрани решение руководителя об учебном допуске.

    Args:
        employee_id: сотрудник маршрута.
        stage_id: завершающее решение.
        data: версия и обоснование.
        context: сервис и проверенный актор.

    Returns:
        Полное состояние после команды.
    """
    return await context.service.approve(context.actor, employee_id, stage_id, data)


@router.post("/{employee_id}/blocker/resolve")
async def resolve_blocker(
    employee_id: UUID, data: CommentInput, context: EmployeesContextDep
) -> DemoStateRead:
    """Зафиксируй устранение условия работодателя.

    Args:
        employee_id: сотрудник с препятствием.
        data: версия и описание решения.
        context: сервис и проверенный актор.

    Returns:
        Полное состояние после команды.
    """
    return await context.service.resolve_blocker(context.actor, employee_id, data)
