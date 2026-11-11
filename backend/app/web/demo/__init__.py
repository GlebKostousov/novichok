"""Экспортируй HTTP-команды демосессии и зависимость проверенного актора."""

from ._deps import ActorDep
from .router import router

__all__ = ["ActorDep", "router"]
