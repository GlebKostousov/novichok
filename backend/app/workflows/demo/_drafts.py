"""Сохрани ввод существующих форм без действий и событий маршрута."""

from uuid import UUID

from app.core.db import UnitOfWork
from app.core.exceptions import InputError, NotFoundError
from app.core.security import DemoActor, DemoRole
from app.entities.demo.drafts import DraftRead, DraftRepo, DraftWrite
from app.entities.demo.exceptions import DraftConflictError
from app.entities.demo.model import DemoDraft
from app.entities.onboarding import OnboardingRepo, StageKey
from app.entities.onboarding.exceptions import RoleForbiddenError


class DraftWorkflow:
    """Проверь область, роль и версию каждого черновика."""

    def __init__(self, uow: UnitOfWork) -> None:
        """Сохрани ресурсы текущего запроса."""
        self._uow = uow
        self._drafts = uow.get_repo(DraftRepo)
        self._routes = uow.get_repo(OnboardingRepo)

    async def read(self, actor: DemoActor) -> list[DraftRead]:
        """Верни черновики собственной учебной области."""
        return [
            DraftRead.model_validate(item)
            for item in await self._drafts.all(actor.workspace_id)
        ]

    async def save(self, actor: DemoActor, key: str, data: DraftWrite) -> DraftRead:
        """Атомарно сравни версию и сохрани ввод без журнала действий."""
        next_version = await self._drafts.lock(actor.workspace_id)
        await self._validate_key(actor, key)
        current = await self._drafts.get(actor.workspace_id, key)
        version = current.version if current is not None else 0
        if version != data.expected_version:
            raise DraftConflictError()
        draft = current or DemoDraft(workspace_id=actor.workspace_id, key=key)
        draft.version = next_version
        draft.fields = data.fields.model_dump(mode="json")
        self._drafts.add(draft)
        await self._uow.commit()
        return DraftRead.model_validate(draft)

    async def _validate_key(self, actor: DemoActor, key: str) -> None:
        """Разреши только ключи существующих форм выбранной роли."""
        if not key.endswith(f":{actor.role.value}"):
            raise RoleForbiddenError()
        if key == "hire:manager":
            return
        parts = _key_parts(key)
        await self._validate_employee_form(actor, parts[0], parts[1])

    async def _validate_employee_form(
        self, actor: DemoActor, person_id: str, form_id: str
    ) -> None:
        """Не различай чужого и отсутствующего сотрудника."""
        employee_id = _employee_id(person_id)
        person = await self._routes.employee(actor.workspace_id, employee_id)
        if person is None:
            raise NotFoundError()
        if form_id == "blocker" and actor.role is DemoRole.MANAGER:
            return
        await self._validate_stage(actor, employee_id, form_id)

    async def _validate_stage(
        self, actor: DemoActor, employee_id: UUID, form_id: str
    ) -> None:
        """Проверь принадлежность этапа и допустимую роль формы."""
        stages = await self._routes.employee_stages(actor.workspace_id, employee_id)
        stage = next((item for item in stages if str(item.id) == form_id), None)
        if stage is None:
            raise NotFoundError()
        _require_stage_role(stage.key, actor.role)


def _employee_id(value: str) -> UUID:
    """Отклони некорректный идентификатор до обращения к хранилищу."""
    try:
        return UUID(value)
    except ValueError as error:
        raise InputError() from error


def _key_parts(key: str) -> list[str]:
    """Ограничь ключ точным составом существующей формы."""
    parts = key.split(":")
    if len(parts) != 3 or len(key) > 100:
        raise InputError()
    return parts


def _require_stage_role(key: StageKey, role: DemoRole) -> None:
    """Сохрани те же границы ролей, что у форм действий."""
    allowed = {
        StageKey.WELCOME: (),
        StageKey.PRODUCT: (DemoRole.EMPLOYEE, DemoRole.MENTOR),
        StageKey.PRACTICE: (DemoRole.MENTOR,),
        StageKey.INDEPENDENT: (DemoRole.MANAGER,),
    }
    if role not in allowed[key]:
        raise RoleForbiddenError()
