"""Предоставь стандартную точку ASGI без открытия ресурсов до lifespan."""

from .app_factory import create_app

app = create_app()
