"""Собери типизированные экранные ответы из сохранённых результатов и программы."""

from collections.abc import Sequence

from app.core.exceptions import AppError
from app.core.security import DemoRole
from app.entities.onboarding import Employee, OnboardingCatalog, Stage, StageStatus
from app.entities.onboarding.schema import (
    BlockerRead,
    EmployeeRead,
    ReviewRead,
    StageRead,
    SubmissionRead,
)


def employee_read(
    employee: Employee, stages: Sequence[Stage], catalog: OnboardingCatalog
) -> EmployeeRead:
    """Верни полный маршрут без дополнительных обращений к базе.

    Args:
        employee: сотрудник текущей области.
        stages: уже прочитанные этапы этого сотрудника.
        catalog: фиксированная программа.

    Returns:
        Полный экранный ответ сотрудника.
    """
    department = catalog.department(employee.department_id)
    return EmployeeRead(
        id=employee.id,
        full_name=employee.full_name,
        position="Продавец-консультант",
        department_id=department.id,
        department_name=department.name,
        start_date=employee.start_date,
        mentor_name=department.mentor_name,
        manager_name=department.manager_name,
        external_id=employee.external_id,
        stages=[_stage_read(stage, employee, catalog) for stage in stages],
        blocker=_blocker_read(employee, department.manager_name),
    )


def _stage_read(
    stage: Stage, employee: Employee, catalog: OnboardingCatalog
) -> StageRead:
    """Добавь инструкцию фиксированной версии к результату этапа.

    Args:
        stage: сохранённый этап.
        employee: владелец маршрута.
        catalog: фиксированная программа.

    Returns:
        Экранный ответ этапа.
    """
    template = catalog.stage(stage.key)
    department = catalog.department(employee.department_id)
    owners = {
        DemoRole.EMPLOYEE: employee.full_name,
        DemoRole.MENTOR: department.mentor_name,
        DemoRole.MANAGER: department.manager_name,
    }
    owner_role = (
        DemoRole.MENTOR
        if stage.status is StageStatus.AWAITING_REVIEW
        else template.owner_role
    )
    return StageRead(
        id=stage.id,
        key=stage.key,
        title=template.title,
        description=template.description,
        kind=template.kind,
        status=stage.status,
        owner_role=owner_role,
        owner_name=owners[owner_role],
        due_date=stage.due_date,
        material_id=template.material_id,
        instructions=template.instructions,
        criteria=list(template.criteria),
        submission=_submission_read(stage),
        review=_review_read(stage),
        completed_at=stage.completed_at,
    )


def _submission_read(stage: Stage) -> SubmissionRead | None:
    """Верни последнюю попытку, не скрывая нарушенную целостность записи.

    Args:
        stage: сохранённый этап.

    Returns:
        Последняя попытка либо отсутствие отправки.
    """
    if stage.submission_text is None:
        return None
    if stage.submitted_at is None:
        raise AppError("Submission has no timestamp")
    return SubmissionRead(
        text=stage.submission_text,
        submitted_at=stage.submitted_at,
        attempt=stage.attempt,
    )


def _review_read(stage: Stage) -> ReviewRead | None:
    """Верни только явно сохранённое решение человека.

    Args:
        stage: сохранённый этап.

    Returns:
        Последнее решение либо отсутствие проверки.
    """
    if stage.review_decision is None:
        return None
    if stage.reviewed_at is None or stage.reviewer_name is None:
        raise AppError("Review has no timestamp or reviewer")
    return ReviewRead(
        decision=stage.review_decision,
        comment=stage.review_comment or "",
        checked_criteria=stage.checked_criteria,
        reviewed_at=stage.reviewed_at,
        reviewer_name=stage.reviewer_name,
    )


def _blocker_read(employee: Employee, manager: str) -> BlockerRead | None:
    """Свяжи препятствие с владельцем условия работодателя.

    Args:
        employee: сотрудник текущей области.
        manager: вымышленный руководитель подразделения.

    Returns:
        Открытое препятствие либо его отсутствие.
    """
    if employee.blocker_reason is None:
        return None
    if employee.blocker_created_at is None:
        raise AppError("Blocker has no timestamp")
    return BlockerRead(
        reason=employee.blocker_reason,
        owner_name=manager,
        created_at=employee.blocker_created_at,
    )
