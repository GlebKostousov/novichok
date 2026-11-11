"""Подготовь три вымышленных маршрута с разными проверяемыми ситуациями."""

from datetime import datetime, timedelta
from uuid import UUID

from app.core.clock import Clock
from app.core.db import UnitOfWork
from app.entities.demo import Activity, DemoRepo
from app.entities.onboarding import (
    Employee,
    OnboardingCatalog,
    OnboardingRepo,
    ReviewDecision,
    Stage,
    StageStatus,
)
from app.entities.onboarding.factory import create_employee


class DemoSeeder:
    """Создай независимый исходный набор внутри общей транзакции."""

    def __init__(
        self, uow: UnitOfWork, *, catalog: OnboardingCatalog, clock: Clock
    ) -> None:
        """Прими репозитории, программу и часы через явные зависимости.

        Args:
            uow: транзакция создания или сброса сессии.
            catalog: фиксированная программа.
            clock: часы процесса.
        """
        self._routes = uow.get_repo(OnboardingRepo)
        self._demo = uow.get_repo(DemoRepo)
        self._catalog = catalog
        self._clock = clock

    async def populate(self, workspace_id: UUID) -> None:
        """Создай стартовое задание, ожидающую проверку и препятствие.

        Args:
            workspace_id: новая либо очищенная область.
        """
        await self._anna(workspace_id)
        await self._dmitry(workspace_id)
        await self._mila(workspace_id)

    def _new(
        self,
        workspace_id: UUID,
        *,
        name: str,
        external_id: str,
        department: str,
        days: int,
    ) -> tuple[Employee, list[Stage]]:
        """Привяжи исходные сроки к сегодняшнему дню.

        Args:
            workspace_id: область демосессии.
            name: вымышленное имя.
            external_id: служебный ключ исходного события.
            department: ключ подразделения.
            days: сколько дней прошло после выхода.

        Returns:
            Сотрудник с новым маршрутом.
        """
        now = self._clock.now()
        return create_employee(
            self._catalog,
            workspace_id=workspace_id,
            external_id=external_id,
            full_name=name,
            department_id=department,
            start_date=now.date() - timedelta(days=days),
            now=now - timedelta(days=days),
        )

    async def _anna(self, workspace_id: UUID) -> None:
        """Подготовь основной сценарий отправки товарного задания.

        Args:
            workspace_id: область демосессии.
        """
        employee, stages = self._new(
            workspace_id,
            name="Анна Синицына",
            external_id="seed-anna",
            department="center",
            days=1,
        )
        _complete(stages[0], self._clock.now() - timedelta(days=1))
        stages[1].status = StageStatus.AVAILABLE
        await self._routes.add(employee, stages)
        self._record(
            employee, "Памятка первого дня изучена. Доступно задание по товару."
        )

    async def _dmitry(self, workspace_id: UUID) -> None:
        """Подготовь ожидающую проверку с прошедшим сроком.

        Args:
            workspace_id: область демосессии.
        """
        employee, stages = self._new(
            workspace_id,
            name="Дмитрий Белов",
            external_id="seed-dmitry",
            department="north",
            days=6,
        )
        _complete(stages[0], self._clock.now() - timedelta(days=6))
        product = stages[1]
        product.status = StageStatus.AWAITING_REVIEW
        product.attempt = 1
        product.submission_text = (
            "Уточню, какими упражнениями и как часто занимается покупатель. "
            "Предложу Arena Flex за 5590 ₽: модель предназначена для зала, "
            "имеет устойчивую подошву и боковую поддержку стопы."
        )
        product.submitted_at = self._clock.now() - timedelta(days=2)
        await self._routes.add(employee, stages)
        self._record(
            employee, "Задание по товару отправлено наставнику. Ожидается проверка."
        )

    async def _mila(self, workspace_id: UUID) -> None:
        """Подготовь практику, остановленную условием работодателя.

        Args:
            workspace_id: область демосессии.
        """
        employee, stages = self._new(
            workspace_id,
            name="Мила Орлова",
            external_id="seed-mila",
            department="center",
            days=4,
        )
        now = self._clock.now()
        _complete(stages[0], now - timedelta(days=4))
        _seed_approved_product(stages[1], now - timedelta(days=1))
        stages[1].reviewer_name = self._catalog.department("center").mentor_name
        stages[2].status = StageStatus.AVAILABLE
        employee.blocker_reason = (
            "Наставнику не выделено время для совместной консультации"
        )
        employee.blocker_created_at = now - timedelta(hours=12)
        await self._routes.add(employee, stages)
        self._record(
            employee, "Товарное задание подтверждено наставником по всем критериям."
        )
        self._record(
            employee,
            "Практика ожидает руководителя: наставнику не выделено время "
            "для совместной консультации.",
        )

    def _record(self, employee: Employee, text: str) -> None:
        """Сохрани явно учебное событие исходного набора.

        Args:
            employee: вымышленный сотрудник.
            text: описание подготовленной ситуации.
        """
        self._demo.add_activity(
            Activity(
                workspace_id=employee.workspace_id,
                employee_id=employee.id,
                actor_name="Демонстрационные данные",
                text=text,
                created_at=self._clock.now() - timedelta(hours=1),
            )
        )


def _complete(stage: Stage, when: datetime) -> None:
    """Зафиксируй завершённый результат исходного набора.

    Args:
        stage: исходный этап.
        when: вымышленный момент завершения.
    """
    stage.status = StageStatus.COMPLETED
    stage.completed_at = when


def _seed_approved_product(stage: Stage, when: datetime) -> None:
    """Подготовь согласованный результат товарного задания.

    Args:
        stage: товарный этап исходного набора.
        when: вымышленный момент проверки.
    """
    _complete(stage, when)
    stage.attempt = 1
    stage.submission_text = (
        "Уточню вид и частоту занятий. Для смешанной тренировки в зале предложу "
        "Arena Flex за 5590 ₽: устойчивая подошва и боковая поддержка подходят "
        "описанной задаче. Предложу примерить пару и проверить посадку."
    )
    stage.submitted_at = when - timedelta(hours=2)
    stage.review_decision = ReviewDecision.APPROVED
    stage.review_comment = "Объяснила выбор и предложила примерить пару."
    stage.checked_criteria = ["needs", "facts", "next_step"]
    stage.reviewed_at = when
