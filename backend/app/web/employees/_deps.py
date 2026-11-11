"""Собери контекст команд маршрута из ресурсов текущего запроса."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends

from app.core.security import DemoActor
from app.web.demo import ActorDep
from app.web.dependencies import RuntimeDep, UowDep
from app.workflows.demo import OnboardingWorkflow


@dataclass(frozen=True, slots=True)
class EmployeesContext:
    """Передай сервис маршрута и актора без обращения роутера к app.state.

    Attributes:
        service: транзакционные команды маршрута.
        actor: проверенная область и выбранная учебная роль.
    """

    service: OnboardingWorkflow
    actor: DemoActor


def get_employees_context(
    uow: UowDep, actor: ActorDep, runtime: RuntimeDep
) -> EmployeesContext:
    """Собери один предметный контекст на запрос.

    Args:
        uow: общая единица работы.
        actor: проверенный контекст посетителя.
        runtime: ресурсы приложения.

    Returns:
        Контекст команд маршрута.
    """
    return EmployeesContext(
        OnboardingWorkflow(uow, catalog=runtime.catalog, clock=runtime.clock), actor
    )


EmployeesContextDep = Annotated[EmployeesContext, Depends(get_employees_context)]
