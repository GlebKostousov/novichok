"""Добавь серверные черновики и уточни исходный вымышленный пример."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_drafts"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Отдели версии черновиков и измени только точные исходные записи Милы."""
    op.add_column(
        "demo_workspaces",
        sa.Column("draft_revision", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_table(
        "demo_drafts",
        sa.Column("workspace_id", sa.Uuid(), primary_key=True),
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["demo_workspaces.id"],
            ondelete="CASCADE",
            name=op.f("fk_demo_drafts_workspace_id_demo_workspaces"),
        ),
        sa.CheckConstraint(
            "version >= 1", name=op.f("ck_demo_drafts_version_positive")
        ),
    )
    employees = sa.table(
        "employees",
        sa.column("id"),
        sa.column("external_id"),
        sa.column("full_name"),
        sa.column("blocker_reason"),
    )
    seed = sa.and_(
        employees.c.external_id == "seed-mila", employees.c.full_name == "Мила Орлова"
    )
    op.execute(
        employees.update()
        .where(
            seed, employees.c.blocker_reason == "Не подготовлен доступ к учебной кассе"
        )
        .values(
            blocker_reason="Наставнику не выделено время для совместной консультации"
        )
    )
    activities = sa.table("activities", sa.column("employee_id"), sa.column("text"))
    op.execute(
        activities.update()
        .where(
            activities.c.employee_id.in_(sa.select(employees.c.id).where(seed)),
            activities.c.text
            == "Практика ожидает руководителя: не подготовлен доступ к учебной кассе.",
        )
        .values(
            text=(
                "Практика ожидает руководителя: наставнику не выделено время "
                "для совместной консультации."
            )
        )
    )


def downgrade() -> None:
    """Удали только новую таблицу; смысл уже прочитанной истории сохрани."""
    op.drop_table("demo_drafts")
    op.drop_column("demo_workspaces", "draft_revision")
