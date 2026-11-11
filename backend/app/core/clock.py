"""Предоставь заменяемые часы для сроков и воспроизводимых тестов."""

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Определи получение текущего момента без зависимости от транспорта."""

    def now(self) -> datetime:
        """Верни текущий момент в UTC."""
        ...


class SystemClock:
    """Используй системное время с явной временной зоной."""

    def now(self) -> datetime:
        """Верни текущий момент в UTC."""
        return datetime.now(UTC)
