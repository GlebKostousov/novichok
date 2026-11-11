"""Сделай фиксацию транзакции явной, а закрытие ресурсов обязательным."""

from types import TracebackType
from typing import Self, cast

from sqlalchemy.ext.asyncio import AsyncSession

from .repository import BaseRepo


class UnitOfWork:
    """Объедини репозитории в одну явно фиксируемую транзакцию."""

    def __init__(self, session: AsyncSession) -> None:
        """Сохрани сессию и пустой реестр репозиториев.

        Args:
            session: сессия текущего сценария.
        """
        self._session = session
        self._repos: dict[type[BaseRepo], BaseRepo] = {}

    async def __aenter__(self) -> Self:
        """Верни контекст без неявного начала или фиксации транзакции."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Откати незавершённую работу и всегда закрой сессию.

        Args:
            exc_type: тип ошибки тела контекста.
            exc: экземпляр ошибки.
            traceback: стек ошибки.
        """
        try:
            await self._session.rollback()
        finally:
            await self._session.close()

    def get_repo[RepoT: BaseRepo](self, repo_class: type[RepoT]) -> RepoT:
        """Верни репозиторий, разделяющий текущую транзакцию.

        Args:
            repo_class: класс нужного репозитория.

        Returns:
            Единственный экземпляр этого репозитория в UnitOfWork.
        """
        if repo_class not in self._repos:
            self._repos[repo_class] = repo_class(self._session)
        # Ключ класса создаётся только вместе с экземпляром того же класса.
        return cast(RepoT, self._repos[repo_class])

    async def flush(self) -> None:
        """Передай изменения базе без фиксации."""
        await self._session.flush()

    async def commit(self) -> None:
        """Зафиксируй весь сценарий одной транзакцией."""
        await self._session.commit()

    async def rollback(self) -> None:
        """Откати изменения перед безопасным повторным чтением."""
        await self._session.rollback()
