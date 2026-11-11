"""Свяжи версию области, предметный переход и аудит одной транзакцией."""

from app.core.clock import Clock
from app.core.db import UnitOfWork
from app.core.security import DemoActor
from app.entities.demo import Activity, DemoRepo, DemoStateRead, LastEventRead
from app.entities.demo.exceptions import StaleStateError
from app.entities.onboarding import TransitionResult

from ._reader import DemoReader


class DemoWriter:
    """Сделай фиксацию всех команд одинаковой и явной."""

    def __init__(self, uow: UnitOfWork, *, reader: DemoReader, clock: Clock) -> None:
        """Сохрани зависимости текущего запроса.

        Args:
            uow: общая транзакция команды.
            reader: сборщик полного состояния.
            clock: часы для аудита.
        """
        self._uow = uow
        self._demo = uow.get_repo(DemoRepo)
        self._reader = reader
        self._clock = clock

    async def begin(self, actor: DemoActor, expected_revision: int) -> None:
        """Займи версию области до чтения изменяемого маршрута.

        Args:
            actor: проверенная область и выбранная роль.
            expected_revision: версия клиента.

        Raises:
            StaleStateError: другой запрос уже изменил состояние.
        """
        if not await self._demo.advance_revision(actor.workspace_id, expected_revision):
            raise StaleStateError()

    def record(self, result: TransitionResult) -> None:
        """Сохрани аудит внутри транзакции предметного перехода.

        Args:
            result: результат сервиса одного маршрута.
        """
        self._demo.add_activity(
            Activity(
                workspace_id=result.employee.workspace_id,
                employee_id=result.employee.id,
                actor_name=result.actor_name,
                text=result.text,
                created_at=self._clock.now(),
            )
        )

    async def finish(
        self, actor: DemoActor, *, last_event: LastEventRead | None = None
    ) -> DemoStateRead:
        """Явно зафиксируй весь сценарий перед выдачей результата.

        Args:
            actor: область выполненной команды.
            last_event: результат кадрового события.

        Returns:
            Полное сохранённое состояние.
        """
        await self._uow.commit()
        return await self._reader.read(actor.workspace_id, last_event=last_event)
