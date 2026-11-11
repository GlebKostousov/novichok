"""Ограничи тело API и потребуй явное действие браузерного демо."""

from fastapi import status
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.exceptions import error_response

MAX_BODY_BYTES = 16 * 1024
MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class _BodyTooLargeError(Exception):
    """Останови чтение входного тела при превышении границы памяти."""


async def _read_body(receive: Receive) -> bytes:
    """Прочитай не более разрешённого количества фактически переданных байтов.

    Args:
        receive: входящий канал ASGI.

    Returns:
        Полное ограниченное тело запроса.
    """
    body = bytearray()
    more_body = True
    while more_body:
        message = await receive()
        chunk = message.get("body", b"")
        _check_size(len(body) + len(chunk))
        body.extend(chunk)
        more_body = message.get("more_body", False)
    return bytes(body)


def _check_size(size: int) -> None:
    """Проверь длину без доверия к Content-Length.

    Args:
        size: уже полученное число байтов.
    """
    if size > MAX_BODY_BYTES:
        raise _BodyTooLargeError()


class _BufferedReceive:
    """Передай проверенное тело приложению ровно один раз."""

    def __init__(self, body: bytes, receive: Receive) -> None:
        """Сохрани тело и исходный канал для последующего отключения клиента.

        Args:
            body: проверенное ограниченное тело.
            receive: первоначальный канал.
        """
        self._body = body
        self._receive = receive
        self._sent = False

    async def __call__(self) -> Message:
        """Выдай тело, затем продолжи исходный ASGI-канал."""
        if self._sent:
            return await self._receive()
        self._sent = True
        return {"type": "http.request", "body": self._body, "more_body": False}


class ApiBoundaryMiddleware:
    """Примени одинаковую границу тела, cookie-команд и кеширования ко всему API."""

    def __init__(self, app: ASGIApp) -> None:
        """Сохрани вложенное приложение.

        Args:
            app: приложение ASGI.
        """
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Пропусти статические ресурсы и проверь только HTTP API.

        Args:
            scope: параметры ASGI-запроса.
            receive: входящий канал.
            send: исходящий канал.
        """
        if scope["type"] != "http" or not scope["path"].startswith("/api"):
            await self._app(scope, receive, send)
            return
        await self._serve_api(scope, receive, send)

    async def _serve_api(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Проверь команду и размер до декодирования JSON приложением.

        Args:
            scope: параметры API-запроса.
            receive: входящий канал.
            send: исходящий канал.
        """
        if not await self._allow_command(scope, receive, send):
            return
        try:
            body = await _read_body(receive)
        except _BodyTooLargeError:
            response = error_response(
                "body_too_large",
                "Запрос превышает допустимый размер 16 KiB.",
                status.HTTP_413_CONTENT_TOO_LARGE,
            )
            await response(scope, receive, send)
            return
        await self._app(scope, _BufferedReceive(body, receive), _ApiSend(send))

    @staticmethod
    async def _allow_command(scope: Scope, receive: Receive, send: Send) -> bool:
        """Потребуй несейфлистовый заголовок для всех изменяющих запросов.

        Args:
            scope: параметры API-запроса.
            receive: входящий канал.
            send: исходящий канал.

        Returns:
            Разрешение передать запрос приложению.
        """
        if scope["method"] not in MUTATING_METHODS:
            return True
        if Headers(scope=scope).get("x-demo-action") == "1":
            return True
        response = error_response(
            "demo_action_required",
            "Для изменения демосессии требуется явное действие интерфейса.",
            status.HTTP_403_FORBIDDEN,
        )
        await response(scope, receive, send)
        return False


class _ApiSend:
    """Запрети кеширование состояния и распознавание неподходящего типа содержимого."""

    def __init__(self, send: Send) -> None:
        """Сохрани исходящий канал.

        Args:
            send: исходящий ASGI-канал.
        """
        self._send = send

    async def __call__(self, message: Message) -> None:
        """Добавь защитные заголовки без изменения тела ответа.

        Args:
            message: исходящее ASGI-сообщение.
        """
        if message["type"] == "http.response.start":
            headers = MutableHeaders(scope=message)
            headers["Cache-Control"] = "no-store"
            headers["X-Content-Type-Options"] = "nosniff"
            headers["Referrer-Policy"] = "same-origin"
        await self._send(message)
