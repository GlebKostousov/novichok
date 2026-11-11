"""Читай и меняй маршрут только внутри явной демонстрационной области."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, func, select

from app.core.db import BaseRepo

from .model import Employee, Stage


class OnboardingRepo(BaseRepo):
    """Собери SQL маршрута без владения commit и без скрытых глобальных выборок."""

    async def employees(self, workspace_id: UUID) -> Sequence[Employee]:
        """Верни ограниченный состав текущей области.

        Args:
            workspace_id: проверенная область cookie.

        Returns:
            Сотрудники в устойчивом порядке создания.
        """
        result = await self._session.scalars(
            select(Employee)
            .where(Employee.workspace_id == workspace_id)
            .order_by(Employee.created_at, Employee.id)
            .limit(20)
            .execution_options(populate_existing=True)
        )
        return result.all()

    async def stages(self, workspace_id: UUID) -> Sequence[Stage]:
        """Прочитай все этапы области одним запросом без N+1.

        Args:
            workspace_id: проверенная область cookie.

        Returns:
            Этапы в последовательности маршрута.
        """
        result = await self._session.scalars(
            select(Stage)
            .join(Employee, Stage.employee_id == Employee.id)
            .where(Employee.workspace_id == workspace_id)
            .order_by(Stage.employee_id, Stage.position)
            .execution_options(populate_existing=True)
        )
        return result.all()

    async def employee(self, workspace_id: UUID, employee_id: UUID) -> Employee | None:
        """Не различай чужой и отсутствующий идентификатор.

        Args:
            workspace_id: проверенная область cookie.
            employee_id: запрошенный сотрудник.

        Returns:
            Сотрудник своей области либо отсутствие результата.
        """
        result = await self._session.execute(
            select(Employee).where(
                Employee.workspace_id == workspace_id, Employee.id == employee_id
            )
        )
        return result.scalar_one_or_none()

    async def by_external_id(
        self, workspace_id: UUID, external_id: str
    ) -> Employee | None:
        """Найди уже обработанное событие в своей области.

        Args:
            workspace_id: проверенная область cookie.
            external_id: ключ кадрового события.

        Returns:
            Ранее созданный сотрудник либо отсутствие результата.
        """
        result = await self._session.execute(
            select(Employee).where(
                Employee.workspace_id == workspace_id,
                Employee.external_id == external_id,
            )
        )
        return result.scalar_one_or_none()

    async def employee_stages(
        self, workspace_id: UUID, employee_id: UUID
    ) -> Sequence[Stage]:
        """Проверь привязку этапов к сотруднику и области одним соединением.

        Args:
            workspace_id: проверенная область cookie.
            employee_id: сотрудник нужного маршрута.

        Returns:
            Этапы только запрошенного маршрута.
        """
        result = await self._session.scalars(
            select(Stage)
            .join(Employee, Stage.employee_id == Employee.id)
            .where(Employee.workspace_id == workspace_id, Employee.id == employee_id)
            .order_by(Stage.position)
        )
        return result.all()

    async def count(self, workspace_id: UUID) -> int:
        """Посчитай сотрудников перед применением лимита.

        Args:
            workspace_id: проверенная область cookie.

        Returns:
            Число сотрудников области.
        """
        result = await self._session.scalar(
            select(func.count())
            .select_from(Employee)
            .where(Employee.workspace_id == workspace_id)
        )
        return result or 0

    async def add(self, employee: Employee, stages: Sequence[Stage]) -> None:
        """Поставь весь маршрут на запись в одной транзакции.

        Args:
            employee: новая кадровая запись.
            stages: четыре её этапа.
        """
        self._session.add(employee)
        # У моделей нет ORM-отношений: родитель фиксируется в flush до зависимых строк.
        await self._session.flush()
        self._session.add_all(stages)

    async def clear(self, workspace_id: UUID) -> None:
        """Сбрось только текущую область с каскадным удалением этапов и истории.

        Args:
            workspace_id: проверенная область cookie.
        """
        await self._session.execute(
            delete(Employee).where(Employee.workspace_id == workspace_id)
        )
