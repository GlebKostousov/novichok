"""Создай новый маршрут с единственным доступным первым этапом."""

from datetime import date, datetime, timedelta
from uuid import UUID, uuid4

from .catalog import OnboardingCatalog
from .enums import StageStatus
from .model import Employee, Stage


def create_employee(
    catalog: OnboardingCatalog,
    *,
    workspace_id: UUID,
    external_id: str,
    full_name: str,
    department_id: str,
    start_date: date,
    now: datetime,
) -> tuple[Employee, list[Stage]]:
    """Рассчитай сроки от фактического выхода без открытия по календарю.

    Args:
        catalog: фиксированная учебная программа.
        workspace_id: область будущего маршрута.
        external_id: устойчивый ключ кадрового события.
        full_name: имя вымышленного сотрудника.
        department_id: существующее подразделение.
        start_date: дата фактического выхода.
        now: момент создания записи.

    Returns:
        Сотрудник и четыре ещё не сохранённых этапа.
    """
    catalog.department(department_id)
    employee = Employee(
        id=uuid4(),
        workspace_id=workspace_id,
        external_id=external_id,
        full_name=full_name,
        department_id=department_id,
        start_date=start_date,
        created_at=now,
        blocker_reason=None,
        blocker_created_at=None,
    )
    stages = [
        Stage(
            id=uuid4(),
            employee_id=employee.id,
            key=template.key,
            position=position,
            status=StageStatus.LOCKED,
            due_date=start_date + timedelta(days=template.due_offset_days),
            attempt=0,
            checked_criteria=[],
        )
        for position, template in enumerate(catalog.stages)
    ]
    stages[0].status = StageStatus.AVAILABLE
    return employee, stages
