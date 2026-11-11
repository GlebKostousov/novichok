"""Проверь процесс и чтение базы без выдачи деталей подключения."""

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import DatabaseUnavailableError

from .dependencies import RuntimeDep

router = APIRouter(tags=["Состояние процесса"])


class HealthRead(BaseModel):
    """Верни короткое подтверждение чтения базы."""

    status: str = "ok"


@router.get("/health")
async def health(runtime: RuntimeDep) -> HealthRead:
    """Проверь чтение базы в текущем процессе.

    Args:
        runtime: ресурсы приложения.

    Returns:
        Успех чтения базы.

    Raises:
        DatabaseUnavailableError: соединение или чтение недоступно.
    """
    try:
        await runtime.database.check_connection()
    except (SQLAlchemyError, OSError) as error:
        raise DatabaseUnavailableError() from error
    return HealthRead()
