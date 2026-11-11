"""Создай изолированные демосессии, маршруты и журнал решений."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создай таблицы в порядке внешних ключей и исходную строку допуска."""
    _create_workspaces()
    _create_employees()
    _create_stages()
    _create_activities()


def _create_workspaces() -> None:
    """Создай области с хешированным токеном и общий замок лимита."""
    op.create_table(
        "demo_admission",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("generation", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint("id = 1", name=op.f("ck_demo_admission_singleton")),
    )
    admission = sa.table("demo_admission", sa.column("id"), sa.column("generation"))
    op.bulk_insert(admission, [{"id": 1, "generation": 1}])
    op.create_table(
        "demo_workspaces",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_event_id", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "revision >= 1", name=op.f("ck_demo_workspaces_revision_positive")
        ),
        sa.UniqueConstraint("token_hash", name=op.f("uq_demo_workspaces_token_hash")),
    )
    op.create_index("ix_demo_workspaces_expires_at", "demo_workspaces", ["expires_at"])


def _create_employees() -> None:
    """Создай кадровые записи с уникальностью события внутри области."""
    op.create_table(
        "employees",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("department_id", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocker_reason", sa.Text(), nullable=True),
        sa.Column("blocker_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["demo_workspaces.id"],
            name=op.f("fk_employees_workspace_id_demo_workspaces"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "workspace_id", "external_id", name=op.f("uq_employees_workspace_id")
        ),
        sa.CheckConstraint(
            "(blocker_reason IS NULL AND blocker_created_at IS NULL) OR "
            "(blocker_reason IS NOT NULL AND blocker_created_at IS NOT NULL)",
            name=op.f("ck_employees_blocker_consistency"),
        ),
    )
    op.create_index("ix_employees_workspace_id", "employees", ["workspace_id"])


def _create_stages() -> None:
    """Создай этапы с проверяемыми значениями и согласованным завершением."""
    op.create_table(
        "stages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("attempt", sa.Integer(), server_default="0", nullable=False),
        sa.Column("submission_text", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_decision", sa.Text(), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("checked_criteria", sa.JSON(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewer_name", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            name=op.f("fk_stages_employee_id_employees"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("employee_id", "key", name=op.f("uq_stages_employee_key")),
        sa.UniqueConstraint(
            "employee_id", "position", name=op.f("uq_stages_employee_position")
        ),
        sa.CheckConstraint(
            "key IN ('welcome', 'product', 'practice', 'independent')",
            name=op.f("ck_stages_key"),
        ),
        sa.CheckConstraint(
            "status IN ('locked', 'available', 'awaiting_review', "
            "'revision_requested', 'completed')",
            name=op.f("ck_stages_status"),
        ),
        sa.CheckConstraint(
            "review_decision IN ('approved', 'changes_requested')",
            name=op.f("ck_stages_review_decision"),
        ),
        sa.CheckConstraint(
            "position >= 0 AND position <= 3", name=op.f("ck_stages_position_range")
        ),
        sa.CheckConstraint("attempt >= 0", name=op.f("ck_stages_attempt_nonnegative")),
        sa.CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL) OR "
            "(status <> 'completed' AND completed_at IS NULL)",
            name=op.f("ck_stages_completion_consistency"),
        ),
    )
    op.create_index("ix_stages_employee_id", "stages", ["employee_id"])


def _create_activities() -> None:
    """Создай ограничиваемую при чтении историю своей области."""
    op.create_table(
        "activities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("actor_name", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["demo_workspaces.id"],
            name=op.f("fk_activities_workspace_id_demo_workspaces"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            name=op.f("fk_activities_employee_id_employees"),
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_activities_workspace_id", "activities", ["workspace_id"])
    op.create_index("ix_activities_employee_id", "activities", ["employee_id"])
    op.create_index("ix_activities_created_at", "activities", ["created_at"])


def downgrade() -> None:
    """Удали таблицы в обратном порядке зависимостей."""
    op.drop_table("activities")
    op.drop_table("stages")
    op.drop_table("employees")
    op.drop_table("demo_workspaces")
    op.drop_table("demo_admission")
