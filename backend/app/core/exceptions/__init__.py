"""Экспортируй общие ошибки и единое преобразование на границе API."""

from .base import AppError, DatabaseUnavailableError, InputError, NotFoundError
from .handlers import error_response, register_error_handlers
from .schema import ErrorEnvelope, ErrorRead

__all__ = [
    "AppError",
    "DatabaseUnavailableError",
    "ErrorEnvelope",
    "ErrorRead",
    "InputError",
    "NotFoundError",
    "error_response",
    "register_error_handlers",
]
