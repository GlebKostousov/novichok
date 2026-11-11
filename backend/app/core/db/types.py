"""Сохрани одинаковые значения enum и UTC в SQLite и PostgreSQL."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, Dialect, Text
from sqlalchemy.types import TypeDecorator


class UtcDateTime(TypeDecorator[datetime]):
    """Восстанови UTC после чтения SQLite, не сохраняющей часовую зону."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        """Нормализуй записываемый момент.

        Args:
            value: момент с явной зоной либо NULL.
            dialect: диалект соединения.

        Returns:
            Момент в UTC либо NULL.
        """
        if value is None:
            return None
        if value.tzinfo is None:
            message = "Для времени обязательна часовая зона"
            raise ValueError(message)
        return value.astimezone(UTC)

    def process_result_value(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        """Прочитай момент в UTC независимо от драйвера.

        Args:
            value: значение базы.
            dialect: диалект соединения.

        Returns:
            Момент с UTC либо NULL.
        """
        if value is None:
            return None
        return (
            value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        )


class EnumText[EnumT: StrEnum](TypeDecorator[EnumT]):
    """Храни строковое перечисление как TEXT с типизированным чтением."""

    impl = Text
    cache_ok = True

    def __init__(self, enum_class: type[EnumT]) -> None:
        """Запомни тип перечисления.

        Args:
            enum_class: допустимые значения колонки.
        """
        super().__init__()
        self.enum_class = enum_class

    def process_bind_param(self, value: EnumT | None, dialect: Dialect) -> str | None:
        """Подготовь значение для записи.

        Args:
            value: перечисление либо NULL.
            dialect: диалект соединения.

        Returns:
            Строка либо NULL.
        """
        return None if value is None else str(value)

    def process_result_value(self, value: str | None, dialect: Dialect) -> EnumT | None:
        """Восстанови перечисление после чтения.

        Args:
            value: строка базы либо NULL.
            dialect: диалект соединения.

        Returns:
            Перечисление либо NULL.
        """
        return None if value is None else self.enum_class(value)


def enum_check(column: str, enum_class: type[StrEnum]) -> CheckConstraint:
    """Ограничи значения enum на уровне базы.

    Args:
        column: внутреннее имя колонки.
        enum_class: тип перечисления из исходного кода.

    Returns:
        Именованное ограничение CHECK.
    """
    values = ", ".join(f"'{item.value}'" for item in enum_class)
    return CheckConstraint(f"{column} IN ({values})", name=column)
