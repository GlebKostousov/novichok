"""Проверь и выполни переходы одного маршрута; фиксацией владеет workflow."""

from uuid import UUID

from app.core.clock import Clock
from app.core.db import UnitOfWork
from app.core.exceptions import NotFoundError
from app.core.security import DemoActor, DemoRole

from ._context import StageContext, TransitionResult
from ._guards import (
    require_previous_completed,
    require_review_comment,
    require_role,
    validate_criteria,
)
from ._transitions import clear_review, complete_stage, record_review
from .catalog import OnboardingCatalog
from .enums import ReviewDecision, StageKey, StageStatus
from .exceptions import EmployerBlockerError, InvalidTransitionError
from .model import Employee
from .repository import OnboardingRepo
from .schema import CommentInput, ObservationCreate, ReviewCreate, SubmissionCreate


class OnboardingService:
    """Сохрани проверки роли и порядка на предметном сервисном слое."""

    def __init__(
        self, uow: UnitOfWork, *, catalog: OnboardingCatalog, clock: Clock
    ) -> None:
        """Прими явные зависимости без HTTP-контекста.

        Args:
            uow: общая транзакция сценария.
            catalog: фиксированные правила маршрута.
            clock: часы текущего процесса.
        """
        self._repo = uow.get_repo(OnboardingRepo)
        self._catalog = catalog
        self._clock = clock

    async def acknowledge(
        self, actor: DemoActor, employee_id: UUID, stage_id: UUID
    ) -> TransitionResult:
        """Подтверди ознакомление и открой изучение товара.

        Args:
            actor: проверенная область и учебная роль.
            employee_id: сотрудник маршрута.
            stage_id: этап ознакомления.

        Returns:
            Доказательство изменения для журнала.
        """
        require_role(actor, DemoRole.EMPLOYEE)
        context = await self._context(actor, employee_id, stage_id)
        self._require_transition(context, StageKey.WELCOME, (StageStatus.AVAILABLE,))
        complete_stage(context, self._clock.now())
        return TransitionResult(
            context.employee,
            context.employee.full_name,
            "Подтверждено ознакомление с памяткой первого дня. "
            "Открыто изучение товара.",
        )

    async def submit(
        self,
        actor: DemoActor,
        employee_id: UUID,
        stage_id: UUID,
        data: SubmissionCreate,
    ) -> TransitionResult:
        """Отправь попытку на проверку, сохранив следующий этап закрытым.

        Args:
            actor: проверенная область и учебная роль.
            employee_id: сотрудник маршрута.
            stage_id: этап товарного задания.
            data: проверенный текст ответа.

        Returns:
            Доказательство отправки для журнала.
        """
        require_role(actor, DemoRole.EMPLOYEE)
        context = await self._context(actor, employee_id, stage_id)
        self._require_transition(
            context,
            StageKey.PRODUCT,
            (StageStatus.AVAILABLE, StageStatus.REVISION_REQUESTED),
        )
        clear_review(context)
        context.stage.attempt += 1
        context.stage.submission_text = data.text
        context.stage.submitted_at = self._clock.now()
        context.stage.status = StageStatus.AWAITING_REVIEW
        return TransitionResult(
            context.employee,
            context.employee.full_name,
            f"Отправлено задание по товару, попытка {context.stage.attempt}. "
            f"{data.text}",
        )

    async def review(
        self,
        actor: DemoActor,
        employee_id: UUID,
        stage_id: UUID,
        data: ReviewCreate,
    ) -> TransitionResult:
        """Прими решение наставника без автоматического анализа ответа.

        Args:
            actor: проверенная область и учебная роль.
            employee_id: сотрудник маршрута.
            stage_id: ожидающее проверки задание.
            data: решение, комментарий и критерии наставника.

        Returns:
            Доказательство решения для журнала.
        """
        require_role(actor, DemoRole.MENTOR)
        context = await self._context(actor, employee_id, stage_id)
        self._require_transition(
            context, StageKey.PRODUCT, (StageStatus.AWAITING_REVIEW,)
        )
        approved = data.decision is ReviewDecision.APPROVED
        validate_criteria(
            context.template, data.checked_criteria, all_required=approved
        )
        return self._apply_assignment_review(context, data)

    async def observe(
        self,
        actor: DemoActor,
        employee_id: UUID,
        stage_id: UUID,
        data: ObservationCreate,
    ) -> TransitionResult:
        """Подтверди наблюдаемую консультацию при готовых условиях работодателя.

        Args:
            actor: проверенная область и учебная роль.
            employee_id: сотрудник маршрута.
            stage_id: этап практики.
            data: наблюдаемые критерии и обратная связь.

        Returns:
            Доказательство подтверждённой практики.
        """
        require_role(actor, DemoRole.MENTOR)
        context = await self._context(actor, employee_id, stage_id)
        self._require_transition(context, StageKey.PRACTICE, (StageStatus.AVAILABLE,))
        self._require_no_blocker(context.employee)
        validate_criteria(context.template, data.checked_criteria, all_required=True)
        reviewer = self._catalog.department(context.employee.department_id).mentor_name
        record_review(
            context,
            decision=ReviewDecision.APPROVED,
            comment=data.comment,
            checked_criteria=data.checked_criteria,
            reviewer_name=reviewer,
            now=self._clock.now(),
        )
        complete_stage(context, self._clock.now())
        return TransitionResult(
            context.employee,
            reviewer,
            f"Практика подтверждена по всем критериям. {data.comment}",
        )

    async def approve(
        self,
        actor: DemoActor,
        employee_id: UUID,
        stage_id: UUID,
        data: CommentInput,
    ) -> TransitionResult:
        """Зафиксируй учебный допуск после всех подтверждённых этапов.

        Args:
            actor: проверенная область и учебная роль.
            employee_id: сотрудник маршрута.
            stage_id: завершающее решение.
            data: обоснование руководителя.

        Returns:
            Доказательство учебного допуска.
        """
        require_role(actor, DemoRole.MANAGER)
        context = await self._context(actor, employee_id, stage_id)
        self._require_transition(
            context, StageKey.INDEPENDENT, (StageStatus.AVAILABLE,)
        )
        self._require_no_blocker(context.employee)
        reviewer = self._catalog.department(context.employee.department_id).manager_name
        record_review(
            context,
            decision=ReviewDecision.APPROVED,
            comment=data.comment,
            checked_criteria=[],
            reviewer_name=reviewer,
            now=self._clock.now(),
        )
        complete_stage(context, self._clock.now())
        return TransitionResult(
            context.employee,
            reviewer,
            f"Разрешены типовые учебные задачи. {data.comment}",
        )

    async def resolve_blocker(
        self, actor: DemoActor, employee_id: UUID, data: CommentInput
    ) -> TransitionResult:
        """Сохрани решение руководителя по существующему препятствию.

        Args:
            actor: проверенная область и учебная роль.
            employee_id: сотрудник с препятствием.
            data: описание устранённого условия.

        Returns:
            Доказательство устранения препятствия.
        """
        require_role(actor, DemoRole.MANAGER)
        employee = await self._employee(actor, employee_id)
        if employee.blocker_reason is None:
            raise InvalidTransitionError(
                public_message="У сотрудника нет открытого препятствия."
            )
        reason = employee.blocker_reason
        employee.blocker_reason = None
        employee.blocker_created_at = None
        manager = self._catalog.department(employee.department_id).manager_name
        return TransitionResult(
            employee,
            manager,
            f"Устранено препятствие: {reason}. Решение: {data.comment}",
        )

    async def _employee(self, actor: DemoActor, employee_id: UUID) -> Employee:
        """Прочитай сотрудника только в проверенной области.

        Args:
            actor: проверенный контекст запроса.
            employee_id: запрошенный сотрудник.

        Returns:
            Сотрудник своей области.

        Raises:
            NotFoundError: сотрудник отсутствует или относится к чужой области.
        """
        employee = await self._repo.employee(actor.workspace_id, employee_id)
        if employee is None:
            raise NotFoundError()
        return employee

    async def _context(
        self, actor: DemoActor, employee_id: UUID, stage_id: UUID
    ) -> StageContext:
        """Проверь привязку запрошенного этапа к доступному сотруднику.

        Args:
            actor: проверенный контекст запроса.
            employee_id: запрошенный сотрудник.
            stage_id: запрошенный этап.

        Returns:
            Контекст одного доступного маршрута.

        Raises:
            NotFoundError: этап отсутствует в маршруте этого сотрудника.
        """
        employee = await self._employee(actor, employee_id)
        stages = await self._repo.employee_stages(actor.workspace_id, employee_id)
        stage = next((item for item in stages if item.id == stage_id), None)
        if stage is None:
            raise NotFoundError()
        return StageContext(
            employee, stage, tuple(stages), self._catalog.stage(stage.key)
        )

    @staticmethod
    def _require_transition(
        context: StageContext, key: StageKey, allowed: tuple[StageStatus, ...]
    ) -> None:
        """Проверь действие, состояние и всех предшественников.

        Args:
            context: доступный маршрут.
            key: этап, которому принадлежит действие.
            allowed: допустимые исходные состояния.
        """
        if context.stage.key is not key or context.stage.status not in allowed:
            raise InvalidTransitionError()
        require_previous_completed(context.stage, context.stages)

    @staticmethod
    def _require_no_blocker(employee: Employee) -> None:
        """Останови допуск при незакрытом условии работодателя.

        Args:
            employee: доступный сотрудник.
        """
        if employee.blocker_reason is not None:
            raise EmployerBlockerError()

    def _apply_assignment_review(
        self, context: StageContext, data: ReviewCreate
    ) -> TransitionResult:
        """Раздели возврат и подтверждение без дублирования записи решения.

        Args:
            context: задание, ожидающее проверки.
            data: проверенный состав решения.

        Returns:
            Доказательство проверки с комментарием для истории.
        """
        reviewer = self._catalog.department(context.employee.department_id).mentor_name
        if data.decision is ReviewDecision.CHANGES_REQUESTED:
            require_review_comment(data.comment)
            context.stage.status = StageStatus.REVISION_REQUESTED
            action = "Задание возвращено на доработку"
        else:
            complete_stage(context, self._clock.now())
            action = "Задание подтверждено по всем критериям; открыта практика"
        record_review(
            context,
            decision=data.decision,
            comment=data.comment,
            checked_criteria=data.checked_criteria,
            reviewer_name=reviewer,
            now=self._clock.now(),
        )
        labels = {item.id: item.label for item in context.template.criteria}
        criteria = (
            ", ".join(labels[key] for key in data.checked_criteria) or "не отмечены"
        )
        return TransitionResult(
            context.employee,
            reviewer,
            f"{action}. Попытка {context.stage.attempt}. "
            f"Критерии: {criteria}. {data.comment}",
        )
