"""Храни маршрут, результат попытки и явное решение проверяющего."""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, EnumText, enum_check

from .enums import ReviewDecision, StageKey, StageStatus


class Employee(Base):
    """Сохрани одно вымышленное трудоустройство в конкретной демосессии."""

    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("workspace_id", "external_id"),
        CheckConstraint(
            "(blocker_reason IS NULL AND blocker_created_at IS NULL) OR "
            "(blocker_reason IS NOT NULL AND blocker_created_at IS NOT NULL)",
            name="blocker_consistency",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("demo_workspaces.id", ondelete="CASCADE"), index=True
    )
    external_id: Mapped[str] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(Text)
    department_id: Mapped[str] = mapped_column(Text)
    start_date: Mapped[date]
    created_at: Mapped[datetime]
    blocker_reason: Mapped[str | None] = mapped_column(Text)
    blocker_created_at: Mapped[datetime | None]


class Stage(Base):
    """Сохрани последовательность и последний результат этапа."""

    __tablename__ = "stages"
    __table_args__ = (
        UniqueConstraint("employee_id", "key", name="uq_stages_employee_key"),
        UniqueConstraint("employee_id", "position", name="uq_stages_employee_position"),
        enum_check("key", StageKey),
        enum_check("status", StageStatus),
        enum_check("review_decision", ReviewDecision),
        CheckConstraint("position >= 0 AND position <= 3", name="position_range"),
        CheckConstraint("attempt >= 0", name="attempt_nonnegative"),
        CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL) OR "
            "(status <> 'completed' AND completed_at IS NULL)",
            name="completion_consistency",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[StageKey] = mapped_column(EnumText(StageKey))
    position: Mapped[int]
    status: Mapped[StageStatus] = mapped_column(EnumText(StageStatus))
    due_date: Mapped[date]
    attempt: Mapped[int] = mapped_column(default=0, server_default="0")
    submission_text: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None]
    review_decision: Mapped[ReviewDecision | None] = mapped_column(
        EnumText(ReviewDecision)
    )
    review_comment: Mapped[str | None] = mapped_column(Text)
    checked_criteria: Mapped[list[str]] = mapped_column(JSON, default=list)
    reviewed_at: Mapped[datetime | None]
    reviewer_name: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None]
