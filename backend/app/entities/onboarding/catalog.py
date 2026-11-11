"""Опиши фиксированный учебный маршрут и назначения вымышленных подразделений."""

from dataclasses import dataclass

from app.core.exceptions import InputError
from app.core.security import DemoRole

from ._materials import build_materials
from .enums import StageKey, StageKind
from .schema import CriterionRead, MaterialRead


@dataclass(frozen=True, slots=True)
class Department:
    """Свяжи подразделение с вымышленными ответственными.

    Attributes:
        id: устойчивый ключ подразделения.
        name: название для интерфейса.
        mentor_name: имя наставника.
        manager_name: имя руководителя.
    """

    id: str
    name: str
    mentor_name: str
    manager_name: str


@dataclass(frozen=True, slots=True)
class StageTemplate:
    """Зафиксируй содержимое и относительный срок этапа.

    Attributes:
        key: устойчивый ключ этапа.
        title: короткое название.
        description: назначение этапа.
        kind: допустимый класс действий.
        owner_role: роль ответственного.
        due_offset_days: календарный срок от фактического выхода.
        material_id: ключ фиксированной версии материала.
        instructions: действие и ожидаемый результат.
        criteria: проверяемые условия результата.
    """

    key: StageKey
    title: str
    description: str
    kind: StageKind
    owner_role: DemoRole
    due_offset_days: int
    material_id: str | None
    instructions: str
    criteria: tuple[CriterionRead, ...]


class OnboardingCatalog:
    """Предоставь небольшую фиксированную учебную программу."""

    def __init__(self) -> None:
        """Собери независимый каталог для экземпляра приложения."""
        self.departments = (
            Department("center", "Магазин · Центр", "Ирина Лазарева", "Олег Миронов"),
            Department("north", "Магазин · Север", "Павел Соколов", "Елена Волкова"),
        )
        self.stages = _build_stages()
        self._departments = {item.id: item for item in self.departments}
        self._stages = {item.key: item for item in self.stages}

    def department(self, department_id: str) -> Department:
        """Верни известное подразделение либо безопасный отказ.

        Args:
            department_id: ключ подразделения из команды или записи.

        Returns:
            Назначения подразделения.

        Raises:
            InputError: подразделение отсутствует в учебном каталоге.
        """
        result = self._departments.get(department_id)
        if result is None:
            raise InputError(
                public_message="Выберите существующее подразделение.",
                field="department_id",
            )
        return result

    def stage(self, key: StageKey) -> StageTemplate:
        """Верни шаблон существующего этапа.

        Args:
            key: проверенный ключ этапа.

        Returns:
            Фиксированное содержимое этапа.
        """
        return self._stages[key]

    def materials(self) -> list[MaterialRead]:
        """Верни независимые DTO учебных материалов."""
        return build_materials()


def _build_stages() -> tuple[StageTemplate, ...]:
    """Определи последовательность без автоматического открытия по сроку."""
    return (
        StageTemplate(
            key=StageKey.WELCOME,
            title="Первый день",
            description="Знакомство с магазином, людьми и условиями работы.",
            kind=StageKind.ACKNOWLEDGEMENT,
            owner_role=DemoRole.EMPLOYEE,
            due_offset_days=0,
            material_id="first-day-v1",
            instructions="Прочитайте памятку первого дня и подтвердите ознакомление.",
            criteria=(),
        ),
        StageTemplate(
            key=StageKey.PRODUCT,
            title="Знание товара",
            description="Подбор модели с аргументами по учебному каталогу.",
            kind=StageKind.ASSIGNMENT,
            owner_role=DemoRole.EMPLOYEE,
            due_offset_days=3,
            material_id="product-catalog-v1",
            instructions=(
                "Покупатель ищет кроссовки для занятий в зале с бюджетом 6000 ₽. "
                "Какие вопросы вы зададите? Предложите модель, обоснуйте выбор "
                "фактами каталога и договоритесь о следующем шаге."
            ),
            criteria=(
                CriterionRead(
                    id="needs", label="Спросил, где и как тренируется покупатель"
                ),
                CriterionRead(id="facts", label="Выбор обоснован фактами каталога"),
                CriterionRead(id="next_step", label="Предложен понятный следующий шаг"),
            ),
        ),
        StageTemplate(
            key=StageKey.PRACTICE,
            title="Практика с наставником",
            description="Проведите консультацию при наставнике.",
            kind=StageKind.OBSERVATION,
            owner_role=DemoRole.MENTOR,
            due_offset_days=7,
            material_id="product-catalog-v1",
            instructions=(
                "Проведите учебную консультацию при наставнике. Наставник отмечает "
                "каждый наблюдаемый критерий и записывает конкретную обратную связь."
            ),
            criteria=(
                CriterionRead(id="contact", label="Выяснена задача покупателя"),
                CriterionRead(id="selection", label="Модель объяснена по каталогу"),
                CriterionRead(id="closing", label="Проведена примерка и подведён итог"),
            ),
        ),
        StageTemplate(
            key=StageKey.INDEPENDENT,
            title="Допуск к типовым задачам",
            description="Решите, какие консультации продавец может проводить сам.",
            kind=StageKind.DECISION,
            owner_role=DemoRole.MANAGER,
            due_offset_days=14,
            material_id=None,
            instructions=(
                "Проверьте результаты предыдущих этапов и отсутствие препятствий. "
                "Зафиксируйте решение о типовых задачах. "
                "Это учебный допуск к типовым консультациям."
            ),
            criteria=(),
        ),
    )
