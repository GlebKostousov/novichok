"""Определи проверяемые команды этапов и экранные ответы маршрута."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer

from app.core.schema import InputSchema
from app.core.security import DemoRole

from .enums import ReviewDecision, StageKey, StageKind, StageStatus


class RevisionInput(InputSchema):
    """Потребуй точную целочисленную версию состояния перед изменением."""

    expected_revision: int = Field(ge=1, le=2_147_483_647, strict=True)


class SubmissionCreate(RevisionInput):
    """Проверь содержательный ответ сотрудника без автоматической оценки."""

    text: str = Field(min_length=30, max_length=2000)


class CommentInput(RevisionInput):
    """Потребуй содержательное пояснение решения человека."""

    comment: str = Field(min_length=10, max_length=1000)


class ObservationCreate(CommentInput):
    """Получай отмеченные критерии наблюдаемой практики."""

    checked_criteria: list[str] = Field(max_length=10)


class ReviewCreate(RevisionInput):
    """Проверь форму решения наставника; состав критериев проверит сервис."""

    decision: ReviewDecision
    comment: str = Field(max_length=1000)
    checked_criteria: list[str] = Field(max_length=10)


class CriterionRead(BaseModel):
    """Опиши проверяемое человеком условие результата."""

    id: str
    label: str


class SubmissionRead(BaseModel):
    """Верни последнюю отправленную попытку."""

    text: str
    submitted_at: datetime
    attempt: int


class ReviewRead(BaseModel):
    """Верни явное решение наставника или руководителя."""

    decision: ReviewDecision
    comment: str
    checked_criteria: list[str]
    reviewed_at: datetime
    reviewer_name: str


class StageRead(BaseModel):
    """Собери инструкцию и актуальное состояние одного этапа."""

    id: UUID
    key: StageKey
    title: str
    description: str
    kind: StageKind
    status: StageStatus
    owner_role: DemoRole
    owner_name: str
    due_date: date
    material_id: str | None
    instructions: str
    criteria: list[CriterionRead]
    submission: SubmissionRead | None
    review: ReviewRead | None
    completed_at: datetime | None


class BlockerRead(BaseModel):
    """Покажи препятствие со стороны работодателя и владельца решения."""

    reason: str
    owner_name: str
    created_at: datetime


class EmployeeRead(BaseModel):
    """Верни полный путь одного вымышленного сотрудника."""

    id: UUID
    full_name: str
    position: str
    department_id: str
    department_name: str
    start_date: date
    mentor_name: str
    manager_name: str
    external_id: str
    stages: list[StageRead]
    blocker: BlockerRead | None


class ProductRead(BaseModel):
    """Опиши вымышленный товар с точной ценой в рублях."""

    id: str
    name: str
    price: Decimal
    purpose: str
    features: list[str]

    @field_serializer("price")
    def serialize_price(self, value: Decimal) -> int:
        """Передай целую цену JSON-числом без двоичной арифметики денег.

        Args:
            value: точная цена каталога в целых рублях.

        Returns:
            Целое количество рублей.
        """
        return int(value)


class MaterialRead(BaseModel):
    """Верни фиксированную версию учебного материала."""

    id: str
    title: str
    version: str
    paragraphs: list[str]
    products: list[ProductRead]
