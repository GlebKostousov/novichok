"""Зафиксируй этапы и допустимые состояния учебного маршрута."""

from enum import StrEnum


class StageKey(StrEnum):
    """Задай устойчивые ключи четырёх этапов."""

    WELCOME = "welcome"
    PRODUCT = "product"
    PRACTICE = "practice"
    INDEPENDENT = "independent"


class StageStatus(StrEnum):
    """Различи доступность, проверку, доработку и подтверждённый результат."""

    LOCKED = "locked"
    AVAILABLE = "available"
    AWAITING_REVIEW = "awaiting_review"
    REVISION_REQUESTED = "revision_requested"
    COMPLETED = "completed"


class StageKind(StrEnum):
    """Различи действие сотрудника, проверку наставника и решение руководителя."""

    ACKNOWLEDGEMENT = "acknowledgement"
    ASSIGNMENT = "assignment"
    OBSERVATION = "observation"
    DECISION = "decision"


class ReviewDecision(StrEnum):
    """Перечисли решения человека по представленному результату."""

    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
