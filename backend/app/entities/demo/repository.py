"""Объедини область, атомарную версию и ограниченный журнал действий."""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select, update

from app.core.db import BaseRepo

from .model import Activity, DemoAdmission, DemoWorkspace


class DemoRepo(BaseRepo):
    """Предоставь SQL сессии без неявного commit."""

    async def lock_admission(self) -> bool:
        """Сериализуй проверку общего лимита через строку, созданную миграцией.

        Returns:
            Признак существования обязательной строки допуска.
        """
        result = await self._session.scalar(
            update(DemoAdmission)
            .where(DemoAdmission.id == 1)
            .values(generation=DemoAdmission.generation + 1)
            .returning(DemoAdmission.id)
        )
        return result is not None

    async def revision(self, workspace_id: UUID) -> int | None:
        """Проверь версию после сборки ответа, не меняя ORM-объект.

        Args:
            workspace_id: проверенная область cookie.

        Returns:
            Текущая версия либо отсутствие области.
        """
        result = await self._session.execute(
            select(DemoWorkspace.revision).where(DemoWorkspace.id == workspace_id)
        )
        return result.scalar_one_or_none()

    async def by_token_hash(
        self, token_hash: str, now: datetime
    ) -> DemoWorkspace | None:
        """Разреши только существующий и неистёкший случайный токен.

        Args:
            token_hash: хеш предъявленного cookie.
            now: текущий момент.

        Returns:
            Активная область либо отсутствие результата.
        """
        result = await self._session.execute(
            select(DemoWorkspace).where(
                DemoWorkspace.token_hash == token_hash,
                DemoWorkspace.expires_at > now,
            )
        )
        return result.scalar_one_or_none()

    async def by_id(self, workspace_id: UUID) -> DemoWorkspace | None:
        """Прочитай свежую версию текущей области.

        Args:
            workspace_id: проверенная область cookie.

        Returns:
            Сохранённая область либо отсутствие результата.
        """
        result = await self._session.execute(
            select(DemoWorkspace)
            .where(DemoWorkspace.id == workspace_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def advance_revision(self, workspace_id: UUID, expected: int) -> bool:
        """Заблокируй изменение по точному сравнению версии в базе.

        Args:
            workspace_id: проверенная область cookie.
            expected: версия, прочитанная клиентом.

        Returns:
            Признак успешного атомарного перехода к следующей версии.
        """
        revision = await self._session.scalar(
            update(DemoWorkspace)
            .where(
                DemoWorkspace.id == workspace_id,
                DemoWorkspace.revision == expected,
            )
            .values(revision=DemoWorkspace.revision + 1)
            .returning(DemoWorkspace.revision)
            .execution_options(synchronize_session=False)
        )
        return revision is not None

    def add(self, workspace: DemoWorkspace) -> None:
        """Поставь новую область на запись.

        Args:
            workspace: подготовленная область с хешем токена.
        """
        self._session.add(workspace)

    def add_activity(self, activity: Activity) -> None:
        """Поставь запись аудита на фиксацию вместе с переходом.

        Args:
            activity: безопасный текст решения и его исполнитель.
        """
        self._session.add(activity)

    async def activities(self, workspace_id: UUID) -> Sequence[Activity]:
        """Верни не более ста последних событий текущей области.

        Args:
            workspace_id: проверенная область cookie.

        Returns:
            События от новых к старым.
        """
        result = await self._session.scalars(
            select(Activity)
            .where(Activity.workspace_id == workspace_id)
            .order_by(Activity.created_at.desc(), Activity.id.desc())
            .limit(100)
        )
        return result.all()

    async def set_last_event(self, workspace_id: UUID, external_id: str | None) -> None:
        """Сохрани ключ последнего созданного сотрудника.

        Args:
            workspace_id: проверенная область cookie.
            external_id: ключ события либо NULL при сбросе.
        """
        await self._session.execute(
            update(DemoWorkspace)
            .where(DemoWorkspace.id == workspace_id)
            .values(last_event_id=external_id)
        )

    async def delete_expired(self, now: datetime) -> None:
        """Освободи истёкшие области перед созданием новой.

        Args:
            now: текущий момент UTC.
        """
        await self._session.execute(
            delete(DemoWorkspace).where(DemoWorkspace.expires_at <= now)
        )

    async def count_active(self, now: datetime) -> int:
        """Посчитай действующие области для ограничения публичного демо.

        Args:
            now: текущий момент UTC.

        Returns:
            Число действующих областей.
        """
        result = await self._session.scalar(
            select(func.count())
            .select_from(DemoWorkspace)
            .where(DemoWorkspace.expires_at > now)
        )
        return result or 0
