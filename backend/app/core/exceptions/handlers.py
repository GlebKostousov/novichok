"""Преобразуй ошибки на одной HTTP-границе без раскрытия внутренних данных."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from app.core.logging import get_logger

from .base import AppError
from .schema import ErrorEnvelope, ErrorRead

logger = get_logger(__name__)


def error_response(
    code: str, message: str, http_status: int, *, field: str | None = None
) -> JSONResponse:
    """Собери одинаковый ответ для прикладных и транспортных ошибок.

    Args:
        code: стабильный машинный код.
        message: безопасное объяснение.
        http_status: статус HTTP.
        field: поле входного запроса.

    Returns:
        JSON без внутренних подробностей.
    """
    body = ErrorEnvelope(error=ErrorRead(code=code, message=message, field=field))
    return JSONResponse(
        body.model_dump(),
        status_code=http_status,
        headers={"Cache-Control": "no-store"},
    )


async def _app_error_handler(request: Request, error: Exception) -> JSONResponse:
    """Переведи прикладной отказ в его публичное представление.

    Args:
        request: текущий запрос.
        error: прикладная ошибка зарегистрированного типа.

    Returns:
        Безопасный ответ.
    """
    if not isinstance(error, AppError):
        return await _unexpected_error_handler(request, error)
    return error_response(
        error.code,
        error.public_message,
        error.http_status,
        field=error.public_field,
    )


async def _validation_handler(request: Request, error: Exception) -> JSONResponse:
    """Скрой входное значение и служебный контекст Pydantic.

    Args:
        request: текущий запрос.
        error: ошибка входной схемы.

    Returns:
        Короткий проверяемый ответ о поле.
    """
    field = None
    if isinstance(error, RequestValidationError) and error.errors():
        field = str(error.errors()[0]["loc"][-1])
    return error_response(
        "validation_error",
        "Проверьте заполнение полей и допустимую длину текста.",
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        field=field,
    )


async def _http_error_handler(request: Request, error: Exception) -> JSONResponse:
    """Верни JSON и для неизвестного API-пути.

    Args:
        request: текущий запрос.
        error: транспортная ошибка.

    Returns:
        Ответ без HTML и внутреннего текста исключения.
    """
    http_status = (
        error.status_code
        if isinstance(error, HTTPException)
        else status.HTTP_500_INTERNAL_SERVER_ERROR
    )
    return error_response("http_error", "Запрос недоступен.", http_status)


async def _unexpected_error_handler(request: Request, error: Exception) -> JSONResponse:
    """Зафиксируй непредвиденную ошибку один раз и скрой детали.

    Args:
        request: текущий запрос.
        error: непредвиденная ошибка.

    Returns:
        Безопасный ответ с ошибкой сервера.
    """
    logger.error("api.unexpected_error", exc_info=error, method=request.method)
    return error_response(
        AppError.code, AppError.public_message, status.HTTP_500_INTERNAL_SERVER_ERROR
    )


def register_error_handlers(app: FastAPI) -> None:
    """Зарегистрируй преобразования в точке сборки приложения.

    Args:
        app: экземпляр FastAPI.
    """
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(HTTPException, _http_error_handler)
    app.add_exception_handler(Exception, _unexpected_error_handler)
