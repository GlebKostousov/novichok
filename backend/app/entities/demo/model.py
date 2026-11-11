"""Храни отдельные демонстрационные области и журнал действий."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DemoAdmission(Base):
    """Сериализуй создание сессий для общего лимита нескольких процессов."""

    __tablename__ = "demo_admission"
    __table_args__ = (CheckConstraint("id = 1", name="singleton"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    generation: Mapped[int] = mapped_column(default=1, server_default="1")


class DemoWorkspace(Base):
    """Свяжи случайный cookie с изолированной областью через хеш."""

    __tablename__ = "demo_workspaces"
    __table_args__ = (CheckConstraint("revision >= 1", name="revision_positive"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    revision: Mapped[int] = mapped_column(default=1, server_default="1")
    draft_revision: Mapped[int] = mapped_column(default=0, server_default="0")
    created_at: Mapped[datetime]
    expires_at: Mapped[datetime] = mapped_column(index=True)
    last_event_id: Mapped[str | None] = mapped_column(Text)


class Activity(Base):
    """Сохрани историю решения в той же транзакции, что изменение этапа."""

    __tablename__ = "activities"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("demo_workspaces.id", ondelete="CASCADE"), index=True
    )
    employee_id: Mapped[UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), index=True
    )
    actor_name: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(index=True)


class DemoDraft(Base):
    """Храни ввод отдельно от действий и версии рабочего процесса."""

    __tablename__ = "demo_drafts"
    __table_args__ = (CheckConstraint("version >= 1", name="version_positive"),)

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("demo_workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    version: Mapped[int]
    fields: Mapped[dict[str, object]] = mapped_column(JSON)
