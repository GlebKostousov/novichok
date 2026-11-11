"""Собери единые проверки роли, порядка этапов и подтверждаемых критериев."""

from collections.abc import Sequence

from app.core.exceptions import InputError
from app.core.security import DemoActor, DemoRole

from .catalog import StageTemplate
from .enums import StageStatus
from .exceptions import CriteriaError, InvalidTransitionError, RoleForbiddenError
from .model import Stage


def require_role(actor: DemoActor, role: DemoRole) -> None:
    """Отклони действие, не соответствующее выбранной учебной роли.

    Args:
        actor: область и роль текущего запроса.
        role: роль, владеющая действием.

    Raises:
        RoleForbiddenError: роли не совпадают.
    """
    if actor.role is not role:
        raise RoleForbiddenError()


def require_previous_completed(stage: Stage, stages: Sequence[Stage]) -> None:
    """Потребуй подтверждённые результаты всех предыдущих этапов.

    Args:
        stage: изменяемый этап.
        stages: этапы того же маршрута.

    Raises:
        InvalidTransitionError: найден незавершённый предшественник.
    """
    previous = (item for item in stages if item.position < stage.position)
    if any(item.status is not StageStatus.COMPLETED for item in previous):
        raise InvalidTransitionError()


def validate_criteria(
    template: StageTemplate,
    checked: list[str],
    *,
    all_required: bool,
) -> None:
    """Проверь точный состав критериев без оценки содержания ответа.

    Args:
        template: фиксированные критерии этапа.
        checked: выбранные наставником идентификаторы.
        all_required: требовать все критерии для подтверждения.

    Raises:
        CriteriaError: есть дубли, неизвестные или пропущенные критерии.
    """
    known = {item.id for item in template.criteria}
    received = set(checked)
    if len(received) != len(checked) or not received.issubset(known):
        raise CriteriaError(field="checked_criteria")
    _require_complete_criteria(known, received, all_required=all_required)


def _require_complete_criteria(
    known: set[str], received: set[str], *, all_required: bool
) -> None:
    """Потребуй полное множество только для положительного решения.

    Args:
        known: все известные критерии.
        received: уникальные выбранные критерии.
        all_required: признак положительного решения.
    """
    if all_required and received != known:
        raise CriteriaError(field="checked_criteria")


def require_review_comment(comment: str) -> None:
    """Потребуй содержательное замечание при возврате работы.

    Args:
        comment: нормализованный комментарий наставника.

    Raises:
        InputError: комментарий слишком короткий.
    """
    if len(comment) < 10:
        raise InputError(
            public_message=(
                "При возврате объясните, что доработать: не менее 10 символов."
            ),
            field="comment",
        )
