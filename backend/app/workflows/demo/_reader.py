"""Собери целостный экранный снимок области несколькими пакетными запросами."""

import re
from collections import defaultdict
from uuid import UUID

from app.core.clock import Clock
from app.core.db import UnitOfWork
from app.entities.demo import DemoRepo, DemoStateRead, LastEventRead
from app.entities.demo.exceptions import SessionRequiredError, StaleStateError
from app.entities.demo.schema import ActivityRead, DepartmentRead
from app.entities.onboarding import OnboardingCatalog, OnboardingRepo, Stage, StageKey

from ._metrics import process_metrics
from ._read_models import employee_read


class DemoReader:
    """Объедини область, маршрут и аудит без N+1."""

    def __init__(
        self, uow: UnitOfWork, *, catalog: OnboardingCatalog, clock: Clock
    ) -> None:
        """Сохрани общую транзакцию и явные источники содержимого.

        Args:
            uow: единица чтения.
            catalog: фиксированная программа.
            clock: текущие часы.
        """
        self._demo = uow.get_repo(DemoRepo)
        self._routes = uow.get_repo(OnboardingRepo)
        self._catalog = catalog
        self._clock = clock

    async def read(
        self, workspace_id: UUID, *, last_event: LastEventRead | None = None
    ) -> DemoStateRead:
        """Верни актуальную версию и данные только одной области.

        Args:
            workspace_id: проверенная область cookie.
            last_event: результат текущего идемпотентного вызова.

        Returns:
            Полное состояние текущей демосессии.

        Raises:
            SessionRequiredError: область больше не существует.
        """
        for _attempt in range(3):
            snapshot = await self._snapshot(workspace_id, last_event=last_event)
            if snapshot.revision == await self._demo.revision(workspace_id):
                return snapshot
        raise StaleStateError()

    async def _snapshot(
        self, workspace_id: UUID, *, last_event: LastEventRead | None
    ) -> DemoStateRead:
        """Собери кандидат снимка для последующей проверки версии.

        Args:
            workspace_id: проверенная область cookie.
            last_event: результат текущего кадрового вызова.

        Returns:
            Снимок с версией, прочитанной до выборки маршрутов.
        """
        workspace = await self._demo.by_id(workspace_id)
        if workspace is None:
            raise SessionRequiredError()
        revision = workspace.revision
        employees = await self._routes.employees(workspace_id)
        stages = await self._routes.stages(workspace_id)
        activities = await self._demo.activities(workspace_id)
        grouped: defaultdict[UUID, list[Stage]] = defaultdict(list)
        for stage in stages:
            grouped[stage.employee_id].append(stage)
        return DemoStateRead(
            revision=revision,
            today=self._clock.now().date(),
            expires_at=workspace.expires_at,
            departments=[
                DepartmentRead(id=item.id, name=item.name)
                for item in self._catalog.departments
            ],
            employees=[
                employee_read(item, grouped[item.id], self._catalog)
                for item in employees
            ],
            materials=self._catalog.materials(),
            activities=[
                ActivityRead.model_validate(item).model_copy(
                    update={"text": _read_activity_text(item.text, self._catalog)}
                )
                for item in activities
            ],
            metrics=process_metrics(employees, stages, self._clock.now().date()),
            last_event=last_event or _last_event(workspace.last_event_id),
        )


def _last_event(external_id: str | None) -> LastEventRead | None:
    """Верни последнее каноническое событие без записи идемпотентного повтора.

    Args:
        external_id: ключ последнего созданного сотрудника.

    Returns:
        Сохранённый результат создания либо отсутствие события.
    """
    if external_id is None:
        return None
    return LastEventRead(external_id=external_id, outcome="created")


def _read_activity_text(text: str, catalog: OnboardingCatalog) -> str:
    """Покажи подписи в старом аудите, не меняя сохранённые решения."""
    labels = {item.id: item.label for item in catalog.stage(StageKey.PRODUCT).criteria}
    return re.sub(
        r"^(Задание [^.]+\. Попытка \d+\. Критерии: )([^.]+)(\.)",
        lambda match: (
            match[1]
            + ", ".join(labels.get(key, key) for key in match[2].split(", "))
            + match[3]
        ),
        text,
    )
