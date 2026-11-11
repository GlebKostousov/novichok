"""Задай общие ORM-типы и стабильные имена ограничений."""

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from sqlalchemy import MetaData, Uuid
from sqlalchemy.orm import DeclarativeBase

from .types import UtcDateTime


class Base(DeclarativeBase):
    """Объедини таблицы приложения в одну явную схему миграций."""

    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )
    type_annotation_map: ClassVar[dict[type, object]] = {
        UUID: Uuid(),
        datetime: UtcDateTime(),
    }
