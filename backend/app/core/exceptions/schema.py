"""Определи единый безопасный ответ для ошибок API."""

from pydantic import BaseModel


class ErrorRead(BaseModel):
    """Верни машинный код, понятный текст и необязательное имя поля."""

    code: str
    message: str
    field: str | None = None


class ErrorEnvelope(BaseModel):
    """Отдели ошибку от успешных ответов одним стабильным ключом."""

    error: ErrorRead
