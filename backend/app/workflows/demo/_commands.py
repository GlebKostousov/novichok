"""Свяжи изменения маршрута с атомарной версией области и аудитом."""

from collections.abc import Awaitable, Callable
from uuid import UUID

from app.core.clock import Clock
from app.core.db import UnitOfWork
from app.core.security import DemoActor
from app.entities.demo import DemoStateRead
from app.entities.onboarding import (
    OnboardingCatalog,
    OnboardingService,
    TransitionResult,
)
from app.entities.onboarding.schema import (
    CommentInput,
    ObservationCreate,
    ReviewCreate,
    RevisionInput,
    SubmissionCreate,
)

from ._reader import DemoReader
from ._writer import DemoWriter


class OnboardingWorkflow:
    """Сохрани результат, следующую доступность и журнал одной транзакцией."""

    def __init__(
        self, uow: UnitOfWork, *, catalog: OnboardingCatalog, clock: Clock
    ) -> None:
        """Свяжи предметный сервис с версией и журналом области.

        Args:
            uow: общая транзакция команды.
            catalog: фиксированные правила маршрута.
            clock: текущие часы.
        """
        self._onboarding = OnboardingService(uow, catalog=catalog, clock=clock)
        reader = DemoReader(uow, catalog=catalog, clock=clock)
        self._writer = DemoWriter(uow, reader=reader, clock=clock)

    async def acknowledge(
        self, actor: DemoActor, employee_id: UUID, stage_id: UUID, data: RevisionInput
    ) -> DemoStateRead:
        """Зафиксируй ознакомление вместе с открытием следующего этапа.

        Args:
            actor: проверенный исполнитель.
            employee_id: сотрудник маршрута.
            stage_id: этап ознакомления.
            data: версия клиента.

        Returns:
            Полное сохранённое состояние.
        """
        return await self._run(
            actor,
            data.expected_revision,
            lambda: self._onboarding.acknowledge(actor, employee_id, stage_id),
        )

    async def submit(
        self,
        actor: DemoActor,
        employee_id: UUID,
        stage_id: UUID,
        data: SubmissionCreate,
    ) -> DemoStateRead:
        """Зафиксируй отправку попытки вместе с историей ответа.

        Args:
            actor: проверенный исполнитель.
            employee_id: сотрудник маршрута.
            stage_id: этап задания.
            data: версия и ответ.

        Returns:
            Полное сохранённое состояние.
        """
        return await self._run(
            actor,
            data.expected_revision,
            lambda: self._onboarding.submit(actor, employee_id, stage_id, data),
        )

    async def review(
        self, actor: DemoActor, employee_id: UUID, stage_id: UUID, data: ReviewCreate
    ) -> DemoStateRead:
        """Зафиксируй возврат либо подтверждение наставника вместе с аудитом.

        Args:
            actor: проверенный исполнитель.
            employee_id: сотрудник маршрута.
            stage_id: проверяемое задание.
            data: версия и явное решение.

        Returns:
            Полное сохранённое состояние.
        """
        return await self._run(
            actor,
            data.expected_revision,
            lambda: self._onboarding.review(actor, employee_id, stage_id, data),
        )

    async def observe(
        self,
        actor: DemoActor,
        employee_id: UUID,
        stage_id: UUID,
        data: ObservationCreate,
    ) -> DemoStateRead:
        """Зафиксируй подтверждённую практику и доступность решения руководителя.

        Args:
            actor: проверенный исполнитель.
            employee_id: сотрудник маршрута.
            stage_id: этап наблюдаемой практики.
            data: версия и подтверждённые критерии.

        Returns:
            Полное сохранённое состояние.
        """
        return await self._run(
            actor,
            data.expected_revision,
            lambda: self._onboarding.observe(actor, employee_id, stage_id, data),
        )

    async def approve(
        self, actor: DemoActor, employee_id: UUID, stage_id: UUID, data: CommentInput
    ) -> DemoStateRead:
        """Зафиксируй учебный допуск и обоснование руководителя.

        Args:
            actor: проверенный исполнитель.
            employee_id: сотрудник маршрута.
            stage_id: этап решения руководителя.
            data: версия и обоснование.

        Returns:
            Полное сохранённое состояние.
        """
        return await self._run(
            actor,
            data.expected_revision,
            lambda: self._onboarding.approve(actor, employee_id, stage_id, data),
        )

    async def resolve_blocker(
        self, actor: DemoActor, employee_id: UUID, data: CommentInput
    ) -> DemoStateRead:
        """Зафиксируй устранение условия работодателя с комментарием.

        Args:
            actor: проверенный исполнитель.
            employee_id: сотрудник с препятствием.
            data: версия и описание решения.

        Returns:
            Полное сохранённое состояние.
        """
        return await self._run(
            actor,
            data.expected_revision,
            lambda: self._onboarding.resolve_blocker(actor, employee_id, data),
        )

    async def _run(
        self,
        actor: DemoActor,
        expected_revision: int,
        operation: Callable[[], Awaitable[TransitionResult]],
    ) -> DemoStateRead:
        """Объедини общие транзакционные гарантии всех предметных действий.

        Args:
            actor: проверенная область и роль.
            expected_revision: версия клиента.
            operation: проверяемое предметное действие.

        Returns:
            Полное состояние после успешного commit.
        """
        await self._writer.begin(actor, expected_revision)
        result = await operation()
        self._writer.record(result)
        return await self._writer.finish(actor)
