"""Идемпотентно свяжи имитацию кадрового события с созданием маршрута."""

from datetime import timedelta

from app.core.clock import Clock
from app.core.db import UnitOfWork
from app.core.exceptions import InputError
from app.core.security import DemoActor, DemoRole
from app.entities.demo import DemoRepo, DemoStateRead, HireCreate, LastEventRead
from app.entities.demo.exceptions import (
    DemoLimitError,
    EventConflictError,
    StaleStateError,
)
from app.entities.onboarding import (
    OnboardingCatalog,
    OnboardingRepo,
    TransitionResult,
    require_role,
)
from app.entities.onboarding.factory import create_employee

from ._reader import DemoReader
from ._writer import DemoWriter


class HireWorkflow:
    """Создай сотрудника, маршрут и аудит в одной транзакции."""

    def __init__(
        self, uow: UnitOfWork, *, catalog: OnboardingCatalog, clock: Clock
    ) -> None:
        """Прими зависимости нормализованного учебного события.

        Args:
            uow: транзакция текущего запроса.
            catalog: фиксированная программа.
            clock: текущие часы.
        """
        self._uow = uow
        self._routes = uow.get_repo(OnboardingRepo)
        self._demo = uow.get_repo(DemoRepo)
        self._catalog = catalog
        self._clock = clock
        self._reader = DemoReader(uow, catalog=catalog, clock=clock)
        self._writer = DemoWriter(uow, reader=self._reader, clock=clock)

    async def hire(self, actor: DemoActor, data: HireCreate) -> DemoStateRead:
        """Проверь повтор раньше версии клиента и не создай второй маршрут.

        Args:
            actor: проверенная область и учебная роль руководителя.
            data: нормализованное событие фактического выхода.

        Returns:
            Существующий либо новый маршрут в полном состоянии демо.
        """
        require_role(actor, DemoRole.MANAGER)
        existing = await self._routes.by_external_id(
            actor.workspace_id, data.external_id
        )
        if existing is not None:
            return await self._repeat(actor, data)
        self._validate_hire(data)
        try:
            await self._writer.begin(actor, data.expected_revision)
        except StaleStateError:
            return await self._after_concurrent_write(actor, data)
        return await self._create(actor, data)

    async def _after_concurrent_write(
        self, actor: DemoActor, data: HireCreate
    ) -> DemoStateRead:
        """Распознай одновременный повтор после отката устаревшей транзакции.

        Args:
            actor: проверенная область.
            data: повторяемое событие.

        Returns:
            Существующий результат того же события.

        Raises:
            StaleStateError: конкурентная запись относится к другому действию.
        """
        await self._uow.rollback()
        existing = await self._routes.by_external_id(
            actor.workspace_id, data.external_id
        )
        if existing is None:
            raise StaleStateError()
        return await self._repeat(actor, data)

    async def _repeat(self, actor: DemoActor, data: HireCreate) -> DemoStateRead:
        """Сравни исходные кадровые поля под неизменным внешним ключом.

        Args:
            actor: проверенная область.
            data: предъявленное событие.

        Returns:
            Сохранённый результат без изменения версии и аудита.

        Raises:
            EventConflictError: ключ использован с другими кадровыми полями.
        """
        snapshot = await self._reader.read(
            actor.workspace_id,
            last_event=LastEventRead(
                external_id=data.external_id, outcome="already_processed"
            ),
        )
        existing = next(
            (
                item
                for item in snapshot.employees
                if item.external_id == data.external_id
            ),
            None,
        )
        if existing is None:
            raise StaleStateError()
        saved = (existing.full_name, existing.department_id, existing.start_date)
        received = (data.full_name, data.department_id, data.start_date)
        if saved != received:
            raise EventConflictError()
        return snapshot

    def _validate_hire(self, data: HireCreate) -> None:
        """Ограничь событие фактическим выходом в пределах прошедшего года.

        Args:
            data: нормализованное событие.

        Raises:
            InputError: подразделение или дата не поддерживаются демо.
        """
        self._catalog.department(data.department_id)
        today = self._clock.now().date()
        if not today - timedelta(days=365) <= data.start_date <= today:
            raise InputError(
                public_message=(
                    "Дата выхода должна быть в пределах последнего года и не в будущем."
                ),
                field="start_date",
            )

    async def _create(self, actor: DemoActor, data: HireCreate) -> DemoStateRead:
        """Создай маршрут под уже занятой атомарной версией области.

        Args:
            actor: проверенная область руководителя.
            data: проверенные кадровые поля.

        Returns:
            Сохранённое состояние с новым сотрудником.
        """
        if await self._routes.count(actor.workspace_id) >= 20:
            raise DemoLimitError()
        employee, stages = create_employee(
            self._catalog,
            workspace_id=actor.workspace_id,
            external_id=data.external_id,
            full_name=data.full_name,
            department_id=data.department_id,
            start_date=data.start_date,
            now=self._clock.now(),
        )
        await self._routes.add(employee, stages)
        await self._demo.set_last_event(actor.workspace_id, data.external_id)
        manager = self._catalog.department(data.department_id).manager_name
        self._writer.record(
            TransitionResult(
                employee,
                manager,
                "Принято учебное событие выхода. Создан маршрут из четырёх этапов.",
            )
        )
        return await self._writer.finish(
            actor,
            last_event=LastEventRead(external_id=data.external_id, outcome="created"),
        )
