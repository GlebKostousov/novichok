"""Экспортируй маршрут, его правила и сервис одного агрегата без HTTP-зависимостей."""

from ._context import TransitionResult
from ._guards import require_role
from .catalog import OnboardingCatalog
from .enums import ReviewDecision, StageKey, StageKind, StageStatus
from .model import Employee, Stage
from .repository import OnboardingRepo
from .service import OnboardingService

__all__ = [
    "Employee",
    "OnboardingCatalog",
    "OnboardingRepo",
    "OnboardingService",
    "ReviewDecision",
    "Stage",
    "StageKey",
    "StageKind",
    "StageStatus",
    "TransitionResult",
    "require_role",
]
