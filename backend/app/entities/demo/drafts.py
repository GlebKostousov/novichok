"""Проверь ограниченные поля черновика и сериализуй конкурентную запись."""

from collections.abc import Sequence
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select, update

from app.core.db import BaseRepo
from app.core.schema import OrmSchema

from .exceptions import SessionRequiredError
from .model import DemoDraft, DemoWorkspace


class DraftFields(BaseModel):
    """Разреши только поля существующих форм, включая незавершённый ввод."""

    model_config = ConfigDict(extra="forbid")
    answer: str = Field(default="", max_length=2000)
    comment: str = Field(default="", max_length=1000)
    checked: list[Annotated[str, Field(max_length=64)]] = Field(
        default_factory=list, max_length=3
    )
    full_name: str = Field(default="", max_length=80)
    department_id: str = Field(default="", max_length=32)
    start_date: str = Field(default="", max_length=10)
    external_id: str = Field(default="", max_length=64)


class DraftWrite(BaseModel):
    """Сравни отдельную версию черновика перед сохранением."""

    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(strict=True, ge=0, le=2**31 - 1)
    fields: DraftFields


class DraftRead(OrmSchema):
    """Верни ключ формы и подтверждённое содержимое."""

    key: str
    version: int
    fields: DraftFields


class DraftRepo(BaseRepo):
    """Храни черновики только в явной области сессии."""

    async def lock(self, workspace_id: UUID) -> int:
        """Сериализуй вставку и сравнение версии без изменения workflow revision."""
        version = await self._session.scalar(
            update(DemoWorkspace)
            .where(DemoWorkspace.id == workspace_id)
            .values(draft_revision=DemoWorkspace.draft_revision + 1)
            .returning(DemoWorkspace.draft_revision)
        )
        if version is None:
            raise SessionRequiredError()
        return version

    async def all(self, workspace_id: UUID) -> Sequence[DemoDraft]:
        """Прочитай только черновики этой области."""
        return (
            await self._session.scalars(
                select(DemoDraft).where(DemoDraft.workspace_id == workspace_id)
            )
        ).all()

    async def get(self, workspace_id: UUID, key: str) -> DemoDraft | None:
        """Найди одну форму внутри проверенной области."""
        result = await self._session.execute(
            select(DemoDraft).where(
                DemoDraft.workspace_id == workspace_id, DemoDraft.key == key
            )
        )
        return result.scalar_one_or_none()

    def add(self, draft: DemoDraft) -> None:
        """Поставь новый черновик на запись."""
        self._session.add(draft)

    async def clear(self, workspace_id: UUID) -> None:
        """Удали ввод при явном сбросе учебного примера."""
        await self._session.execute(
            delete(DemoDraft).where(DemoDraft.workspace_id == workspace_id)
        )
