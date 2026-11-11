"""Свяжи репозитории с сессией, оставив фиксацию владельцу сценария."""

from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepo:
    """Предоставь одну сессию производным репозиториям."""

    def __init__(self, session: AsyncSession) -> None:
        """Сохрани сессию текущей транзакции.

        Args:
            session: сессия, принадлежащая UnitOfWork.
        """
        self._session = session
