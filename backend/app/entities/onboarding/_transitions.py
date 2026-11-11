"""Измени проверенный этап без самостоятельного commit."""

from datetime import datetime

from ._context import StageContext
from .enums import ReviewDecision, StageStatus


def complete_stage(context: StageContext, now: datetime) -> None:
    """Закрой текущий этап и открой единственного непосредственного преемника.

    Args:
        context: маршрут с уже проверенными ролью и переходом.
        now: момент подтверждения результата.
    """
    context.stage.status = StageStatus.COMPLETED
    context.stage.completed_at = now
    next_stage = next(
        (
            item
            for item in context.stages
            if item.position == context.stage.position + 1
        ),
        None,
    )
    if next_stage is not None:
        next_stage.status = StageStatus.AVAILABLE


def clear_review(context: StageContext) -> None:
    """Очисти последнее решение перед новой попыткой, сохранив прежнее в журнале.

    Args:
        context: проверенный маршрут повторной отправки.
    """
    stage = context.stage
    stage.review_decision = None
    stage.review_comment = None
    stage.checked_criteria = []
    stage.reviewed_at = None
    stage.reviewer_name = None


def record_review(
    context: StageContext,
    *,
    decision: ReviewDecision,
    comment: str,
    checked_criteria: list[str],
    reviewer_name: str,
    now: datetime,
) -> None:
    """Сохрани явное решение человека и состав подтверждённых критериев.

    Args:
        context: проверенный маршрут.
        decision: решение проверяющего.
        comment: его комментарий.
        checked_criteria: проверенные идентификаторы критериев.
        reviewer_name: вымышленное имя проверяющего.
        now: момент решения.
    """
    stage = context.stage
    stage.review_decision = decision
    stage.review_comment = comment
    stage.checked_criteria = checked_criteria
    stage.reviewed_at = now
    stage.reviewer_name = reviewer_name
