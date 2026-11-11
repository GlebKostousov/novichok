"""Передай проверенный маршрут между небольшими операциями сервиса."""

from dataclasses import dataclass

from .catalog import StageTemplate
from .model import Employee, Stage


@dataclass(frozen=True, slots=True)
class StageContext:
    """Собери данные только одного сотрудника проверенной области.

    Attributes:
        employee: сотрудник своей демонстрационной области.
        stage: запрошенный этап того же сотрудника.
        stages: упорядоченный маршрут.
        template: фиксированные правила этапа.
    """

    employee: Employee
    stage: Stage
    stages: tuple[Stage, ...]
    template: StageTemplate


@dataclass(frozen=True, slots=True)
class TransitionResult:
    """Верни доказательство изменения для записи аудита вызывающим сценарием.

    Attributes:
        employee: сотрудник, чей маршрут изменён.
        actor_name: имя вымышленного исполнителя действия.
        text: безопасное описание действия и явного решения.
    """

    employee: Employee
    actor_name: str
    text: str
