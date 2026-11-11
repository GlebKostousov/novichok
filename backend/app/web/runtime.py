"""Свяжи ресурсы lifespan с типизированными зависимостями HTTP-запроса."""

from dataclasses import dataclass

from app.core.clock import Clock
from app.core.config import Settings
from app.core.db import Database
from app.entities.onboarding import OnboardingCatalog


@dataclass(frozen=True, slots=True)
class Runtime:
    """Передай явно принадлежащие приложению ресурсы.

    Attributes:
        database: владелец движка и фабрики транзакций.
        settings: проверенные настройки запуска.
        clock: источник текущего времени.
        catalog: фиксированная учебная программа.
    """

    database: Database
    settings: Settings
    clock: Clock
    catalog: OnboardingCatalog
