"""Опиши явную демонстрационную роль и границу рабочей области."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class DemoRole(StrEnum):
    """Перечисли роли учебного сценария без утверждения личности."""

    EMPLOYEE = "employee"
    MENTOR = "mentor"
    MANAGER = "manager"


@dataclass(frozen=True, slots=True)
class DemoActor:
    """Передай проверенную область cookie и выбранную учебную роль.

    Attributes:
        workspace_id: рабочая область текущей демонстрационной сессии.
        role: выбранная посетителем роль.
    """

    workspace_id: UUID
    role: DemoRole
