"""Раздели безопасный публичный ответ и внутренний контекст ошибки."""

from fastapi import status


class AppError(Exception):
    """Задай стабильный код и HTTP-представление прикладной ошибки."""

    code = "internal_error"
    http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    public_message = "Не удалось выполнить запрос. Попробуйте ещё раз."

    def __init__(
        self,
        internal_message: str | None = None,
        *,
        public_message: str | None = None,
        field: str | None = None,
    ) -> None:
        """Сохрани внутреннее сообщение отдельно от публичного.

        Args:
            internal_message: техническое объяснение без секретов.
            public_message: безопасный текст, уточняющий отказ.
            field: имя поля запроса, связанного с ошибкой.
        """
        self.public_message = public_message or self.public_message
        self.public_field = field
        self.internal_message = internal_message or self.public_message
        super().__init__(self.internal_message)


class NotFoundError(AppError):
    """Не различай неизвестный объект и объект чужой сессии."""

    code = "not_found"
    http_status = status.HTTP_404_NOT_FOUND
    public_message = "Запись не найдена в этой демонстрационной сессии."


class InputError(AppError):
    """Сообщи о нарушении проверяемого входного контракта."""

    code = "validation_error"
    http_status = status.HTTP_422_UNPROCESSABLE_CONTENT
    public_message = "Проверьте заполнение полей."


class DatabaseUnavailableError(AppError):
    """Сообщи о временной недоступности без деталей подключения."""

    code = "database_unavailable"
    http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    public_message = "Хранилище временно недоступно. Попробуйте позже."
