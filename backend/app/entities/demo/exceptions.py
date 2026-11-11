"""Опиши отказы сессии, версии и повторного кадрового события."""

from fastapi import status

from app.core.exceptions import AppError


class SessionRequiredError(AppError):
    """Потребуй действующий cookie перед любой командой."""

    code = "session_required"
    http_status = status.HTTP_401_UNAUTHORIZED
    public_message = "Демосессия закончилась. Обновите страницу."


class StaleStateError(AppError):
    """Останови запись поверх более свежего состояния."""

    code = "stale_state"
    http_status = status.HTTP_409_CONFLICT
    public_message = "Состояние уже изменилось. Обновите данные и повторите действие."


class DraftConflictError(AppError):
    """Останови тихую перезапись черновика из другой вкладки."""

    code = "draft_conflict"
    http_status = status.HTTP_409_CONFLICT
    public_message = "Черновик изменён в другом окне. Ваш ввод остаётся в этой вкладке."


class EventConflictError(AppError):
    """Отклони несовпадающие кадровые поля под прежним ключом события."""

    code = "event_conflict"
    http_status = status.HTTP_409_CONFLICT
    public_message = "Событие с таким номером уже принято с другими данными."


class DemoLimitError(AppError):
    """Ограничь число вымышленных сотрудников одной демонстрационной области."""

    code = "demo_limit"
    http_status = status.HTTP_409_CONFLICT
    public_message = "В демосессии может быть не более 20 сотрудников."


class DemoCapacityError(AppError):
    """Останови создание областей при исчерпании общего лимита демо."""

    code = "demo_capacity"
    http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    public_message = "Демо временно достигло лимита новых сессий. Попробуйте позже."
