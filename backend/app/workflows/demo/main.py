"""Создай, прочитай и сбрось изолированную демонстрационную сессию."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from app.core.clock import Clock
from app.core.db import UnitOfWork
from app.core.exceptions import AppError
from app.core.security import DemoActor
from app.entities.demo import DemoRepo, DemoStateRead, DemoWorkspace
from app.entities.demo.drafts import DraftRepo
from app.entities.demo.exceptions import DemoCapacityError, SessionRequiredError
from app.entities.onboarding import OnboardingCatalog, OnboardingRepo
from app.entities.onboarding.schema import RevisionInput

from ._reader import DemoReader
from ._seed import DemoSeeder
from ._writer import DemoWriter

SESSION_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
COOKIE_NAME = "novichok_demo"


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    """Отдели публичное состояние от токена, который попадёт только в cookie.

    Attributes:
        state: публичный снимок демосессии.
        new_token: новый непрозрачный токен либо отсутствие обновления cookie.
    """

    state: DemoStateRead
    new_token: str | None


class DemoService:
    """Оркестрируй область с маршрутами, сохраняя token вне JSON-ответов."""

    def __init__(
        self,
        uow: UnitOfWork,
        *,
        catalog: OnboardingCatalog,
        clock: Clock,
        max_workspaces: int,
    ) -> None:
        """Прими настройки и ресурсы из точки сборки запроса.

        Args:
            uow: текущая единица работы.
            catalog: фиксированная учебная программа.
            clock: текущие часы.
            max_workspaces: общий лимит одновременно действующих областей.
        """
        self._uow = uow
        self._demo = uow.get_repo(DemoRepo)
        self._routes = uow.get_repo(OnboardingRepo)
        self._clock = clock
        self._max_workspaces = max_workspaces
        self._reader = DemoReader(uow, catalog=catalog, clock=clock)
        self._seeder = DemoSeeder(uow, catalog=catalog, clock=clock)
        self._writer = DemoWriter(uow, reader=self._reader, clock=clock)

    async def bootstrap(self, token: str | None) -> BootstrapResult:
        """Продолжи действующую область либо создай новую из синтетики.

        Args:
            token: предъявленный непрозрачный cookie либо его отсутствие.

        Returns:
            Полное состояние и необязательный новый cookie.
        """
        workspace = await self._resolve(token)
        if workspace is not None:
            return BootstrapResult(await self._reader.read(workspace.id), None)
        return await self._create_session()

    async def workspace_id(self, token: str | None) -> UUID:
        """Разреши команду только внутри действующей области cookie.

        Args:
            token: непрозрачный cookie текущего браузера.

        Returns:
            Проверенный идентификатор области.

        Raises:
            SessionRequiredError: cookie отсутствует, неизвестен или истёк.
        """
        workspace = await self._resolve(token)
        if workspace is None:
            raise SessionRequiredError()
        return workspace.id

    async def reset(self, actor: DemoActor, data: RevisionInput) -> DemoStateRead:
        """Замени начальными данными только собственную область.

        Args:
            actor: проверенная область и любая допустимая учебная роль.
            data: прочитанная клиентом версия.

        Returns:
            Новый начальный набор с увеличенной версией.
        """
        await self._writer.begin(actor, data.expected_revision)
        await self._uow.get_repo(DraftRepo).clear(actor.workspace_id)
        await self._routes.clear(actor.workspace_id)
        await self._demo.set_last_event(actor.workspace_id, None)
        await self._seeder.populate(actor.workspace_id)
        return await self._writer.finish(actor)

    async def _resolve(self, token: str | None) -> DemoWorkspace | None:
        """Не используй предъявленный cookie как идентификатор области.

        Args:
            token: непрозрачное значение cookie.

        Returns:
            Активная область, найденная по хешу, либо отсутствие результата.
        """
        if token is None or len(token) != 43:
            return None
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return await self._demo.by_token_hash(digest, self._clock.now())

    async def _create_session(self) -> BootstrapResult:
        """Проверь общий лимит и атомарно создай полный исходный набор.

        Returns:
            Сохранённое состояние с новым непрозрачным токеном.

        Raises:
            DemoCapacityError: исчерпан общий лимит публичного демо.
        """
        await self._admit_session()
        token = secrets.token_urlsafe(32)
        now = self._clock.now()
        workspace = DemoWorkspace(
            id=uuid4(),
            token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            revision=1,
            created_at=now,
            expires_at=now + timedelta(seconds=SESSION_MAX_AGE_SECONDS),
            last_event_id=None,
        )
        self._demo.add(workspace)
        await self._uow.flush()
        await self._seeder.populate(workspace.id)
        await self._uow.commit()
        return BootstrapResult(await self._reader.read(workspace.id), token)

    async def _admit_session(self) -> None:
        """Сериализуй очистку и общий лимит между процессами через базу."""
        if not await self._demo.lock_admission():
            raise AppError("Demo admission row is missing; apply migrations")
        now = self._clock.now()
        await self._demo.delete_expired(now)
        if await self._demo.count_active(now) >= self._max_workspaces:
            raise DemoCapacityError()
