"""Вычисли счётчики только из текущих записей учебного процесса."""

from collections.abc import Sequence
from datetime import date

from app.entities.demo.schema import ProcessMetrics
from app.entities.onboarding import Employee, Stage, StageKey, StageStatus


def process_metrics(
    employees: Sequence[Employee], stages: Sequence[Stage], today: date
) -> ProcessMetrics:
    """Не подменяй рабочие счётчики процентами эффекта на моковых данных.

    Args:
        employees: сотрудники текущей области.
        stages: этапы их маршрутов.
        today: текущая календарная дата UTC.

    Returns:
        Фактические счётчики состояния.
    """
    return ProcessMetrics(
        employees_total=len(employees),
        completed_stages=sum(stage.status is StageStatus.COMPLETED for stage in stages),
        stages_total=len(stages),
        awaiting_review=sum(
            stage.status is StageStatus.AWAITING_REVIEW for stage in stages
        ),
        overdue_stages=sum(_is_overdue(stage, today) for stage in stages),
        blocked_employees=sum(
            employee.blocker_reason is not None for employee in employees
        ),
        independent_employees=sum(_is_independent(stage) for stage in stages),
    )


def _is_overdue(stage: Stage, today: date) -> bool:
    """Учитывай просрочку только открытых незавершённых этапов.

    Args:
        stage: этап текущей области.
        today: текущая календарная дата.

    Returns:
        Признак прошедшего срока открытого этапа.
    """
    return (
        stage.status not in (StageStatus.LOCKED, StageStatus.COMPLETED)
        and stage.due_date < today
    )


def _is_independent(stage: Stage) -> bool:
    """Учитывай только подтверждённый руководителем учебный допуск.

    Args:
        stage: этап текущей области.

    Returns:
        Признак завершённого допуска.
    """
    return stage.key is StageKey.INDEPENDENT and stage.status is StageStatus.COMPLETED
