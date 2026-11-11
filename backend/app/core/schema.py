"""Задай общие правила проверяемых входов и читаемых ответов."""

from pydantic import BaseModel, ConfigDict, field_validator


class InputSchema(BaseModel):
    """Запрети неизвестные поля и убери внешние пробелы в строках."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*", mode="before")
    @classmethod
    def reject_null_character(cls, value: object) -> object:
        """Сохрани одинаковый контракт текста в PostgreSQL и SQLite.

        Args:
            value: значение входного поля до предметной проверки.

        Returns:
            Значение без запрещённого PostgreSQL нулевого символа.
        """
        if isinstance(value, str) and "\x00" in value:
            message = "Текст не должен содержать нулевой управляющий символ"
            raise ValueError(message)
        return value


class OrmSchema(BaseModel):
    """Разреши материализацию ответов из типизированных ORM-объектов."""

    model_config = ConfigDict(from_attributes=True)
