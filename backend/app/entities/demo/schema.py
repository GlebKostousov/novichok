"""Определи единое состояние демо и нормализованное событие выхода."""

import re
import unicodedata
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.schema import OrmSchema
from app.entities.onboarding.schema import (
    EmployeeRead,
    MaterialRead,
    RevisionInput,
)


class HireCreate(RevisionInput):
    """Проверь форму имитации события фактического выхода сотрудника."""

    external_id: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    full_name: str = Field(min_length=2, max_length=80)
    department_id: str = Field(min_length=1, max_length=32)
    start_date: date

    @field_validator("start_date", mode="before")
    @classmethod
    def require_calendar_date(cls, value: object) -> object:
        """Принимай календарную дату, не timestamp или дату-время.

        Args:
            value: входное значение JSON либо дата внутреннего вызова.

        Returns:
            Значение для стандартной проверки календаря Pydantic.
        """
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return value
        message = "Используйте календарную дату YYYY-MM-DD"
        raise ValueError(message)

    @field_validator("full_name")
    @classmethod
    def reject_control_characters(cls, value: str) -> str:
        """Отклони управляющие и скрытые служебные символы в имени.

        Args:
            value: нормализованное имя.

        Returns:
            Проверенное имя.
        """
        if any(unicodedata.category(char).startswith("C") for char in value):
            message = "Имя не должно содержать управляющие символы"
            raise ValueError(message)
        return value


class DepartmentRead(BaseModel):
    """Опиши вымышленное подразделение."""

    id: str
    name: str


class ActivityRead(OrmSchema):
    """Верни сохранённую запись журнала."""

    id: UUID
    employee_id: UUID
    actor_name: str
    text: str
    created_at: datetime


class ProcessMetrics(BaseModel):
    """Покажи фактические счётчики текущего процесса без обещаний эффекта."""

    employees_total: int
    completed_stages: int
    stages_total: int
    awaiting_review: int
    overdue_stages: int
    blocked_employees: int
    independent_employees: int


class LastEventRead(BaseModel):
    """Покажи результат обработки имитированного кадрового события."""

    external_id: str
    outcome: Literal["created", "already_processed"]


class DemoStateRead(BaseModel):
    """Верни целостный экранный снимок текущей демонстрационной области."""

    revision: int
    today: date
    expires_at: datetime
    departments: list[DepartmentRead]
    employees: list[EmployeeRead]
    materials: list[MaterialRead]
    activities: list[ActivityRead]
    metrics: ProcessMetrics
    last_event: LastEventRead | None
