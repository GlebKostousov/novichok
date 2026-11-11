"""Опиши предметные отказы без транспортных обработчиков в сервисах."""

from fastapi import status

from app.core.exceptions import AppError, InputError


class RoleForbiddenError(AppError):
    """Отклони действие другой учебной роли на сервисном слое."""

    code = "role_forbidden"
    http_status = status.HTTP_403_FORBIDDEN
    public_message = "Для этого действия выберите соответствующую роль в демо."


class InvalidTransitionError(AppError):
    """Отклони повторный или преждевременный переход."""

    code = "invalid_transition"
    http_status = status.HTTP_409_CONFLICT
    public_message = "Этот этап сейчас не допускает выбранное действие."


class EmployerBlockerError(AppError):
    """Останови допуск, пока работодатель не устранит препятствие."""

    code = "employer_blocker"
    http_status = status.HTTP_409_CONFLICT
    public_message = "Сначала руководитель должен устранить препятствие работодателя."


class CriteriaError(InputError):
    """Отклони неизвестные, повторённые или незаполненные критерии."""

    code = "invalid_criteria"
    public_message = (
        "Проверьте критерии: для подтверждения нужны все пункты без повторов."
    )
