"""Проверь переход от кадрового события до явного допуска человека."""

from httpx import AsyncClient

from app.core.security import DemoRole
from app.entities.demo import HireCreate
from app.entities.onboarding import ReviewDecision, StageKey, StageStatus
from app.entities.onboarding.schema import (
    CommentInput,
    ObservationCreate,
    ReviewCreate,
    RevisionInput,
    SubmissionCreate,
)

from .helpers import (
    ANSWER,
    COMMENT,
    assert_error,
    bootstrap,
    employee,
    post,
    stage,
    stage_path,
    success,
)


async def test_full_journey_requires_review_and_preserves_revision_history(
    client: AsyncClient,
) -> None:
    """Пройди найм, возврат, повторную проверку, практику и допуск.

    Args:
        client: изолированный HTTP-клиент.
    """
    state = await bootstrap(client)
    state = await success(
        client,
        "/api/demo/hire",
        DemoRole.MANAGER,
        HireCreate(
            expected_revision=state.revision,
            external_id="test-full-route",
            full_name="Тестовый Сотрудник",
            department_id="center",
            start_date=state.today,
        ),
    )
    person = employee(state, "test-full-route")
    assert [item.status for item in person.stages] == [
        StageStatus.AVAILABLE,
        StageStatus.LOCKED,
        StageStatus.LOCKED,
        StageStatus.LOCKED,
    ]
    premature = await post(
        client,
        stage_path(person, StageKey.INDEPENDENT, "approve"),
        DemoRole.MANAGER,
        CommentInput(expected_revision=state.revision, comment=COMMENT),
    )
    assert_error(premature, 409, "invalid_transition")
    state = await success(
        client,
        stage_path(person, StageKey.WELCOME, "acknowledge"),
        DemoRole.EMPLOYEE,
        RevisionInput(expected_revision=state.revision),
    )
    state = await success(
        client,
        stage_path(person, StageKey.PRODUCT, "submit"),
        DemoRole.EMPLOYEE,
        SubmissionCreate(expected_revision=state.revision, text=ANSWER),
    )
    product = stage(employee(state, "test-full-route"), StageKey.PRODUCT)
    assert product.status is StageStatus.AWAITING_REVIEW
    assert product.owner_role is DemoRole.MENTOR
    assert product.owner_name == person.mentor_name
    assert (
        stage(employee(state, "test-full-route"), StageKey.PRACTICE).status
        is StageStatus.LOCKED
    )
    return_comment = "Добавьте конкретное предложение примерить подходящую пару."
    state = await success(
        client,
        stage_path(person, StageKey.PRODUCT, "review"),
        DemoRole.MENTOR,
        ReviewCreate(
            expected_revision=state.revision,
            decision=ReviewDecision.CHANGES_REQUESTED,
            comment=return_comment,
            checked_criteria=["needs", "facts"],
        ),
    )
    product = stage(employee(state, "test-full-route"), StageKey.PRODUCT)
    assert product.status is StageStatus.REVISION_REQUESTED
    assert product.owner_role is DemoRole.EMPLOYEE
    assert product.owner_name == person.full_name
    assert product.submission is not None and product.submission.attempt == 1
    state = await success(
        client,
        stage_path(person, StageKey.PRODUCT, "submit"),
        DemoRole.EMPLOYEE,
        SubmissionCreate(expected_revision=state.revision, text=ANSWER),
    )
    product = stage(employee(state, "test-full-route"), StageKey.PRODUCT)
    assert product.submission is not None and product.submission.attempt == 2
    assert product.review is None
    assert any(return_comment in item.text for item in state.activities)
    state = await success(
        client,
        stage_path(person, StageKey.PRODUCT, "review"),
        DemoRole.MENTOR,
        ReviewCreate(
            expected_revision=state.revision,
            decision=ReviewDecision.APPROVED,
            comment=COMMENT,
            checked_criteria=["needs", "facts", "next_step"],
        ),
    )
    practice = stage(employee(state, "test-full-route"), StageKey.PRACTICE)
    assert practice.status is StageStatus.AVAILABLE
    state = await success(
        client,
        stage_path(person, StageKey.PRACTICE, "observe"),
        DemoRole.MENTOR,
        ObservationCreate(
            expected_revision=state.revision,
            comment=COMMENT,
            checked_criteria=[item.id for item in practice.criteria],
        ),
    )
    state = await success(
        client,
        stage_path(person, StageKey.INDEPENDENT, "approve"),
        DemoRole.MANAGER,
        CommentInput(expected_revision=state.revision, comment=COMMENT),
    )
    assert all(
        item.status is StageStatus.COMPLETED
        for item in employee(state, "test-full-route").stages
    )
    assert state.metrics.independent_employees == 1
    assert (await bootstrap(client)) == state
    repeated = await post(
        client,
        stage_path(person, StageKey.PRODUCT, "submit"),
        DemoRole.EMPLOYEE,
        SubmissionCreate(expected_revision=state.revision, text=ANSWER),
    )
    assert_error(repeated, 409, "invalid_transition")
    assert (await bootstrap(client)) == state


async def test_employer_blocker_requires_manager_resolution(
    client: AsyncClient,
) -> None:
    """Не разрешай наставнику провести практику до подготовки работодателя.

    Args:
        client: изолированный HTTP-клиент.
    """
    state = await bootstrap(client)
    person = employee(state, "seed-mila")
    practice = stage(person, StageKey.PRACTICE)
    observation = ObservationCreate(
        expected_revision=state.revision,
        comment=COMMENT,
        checked_criteria=[item.id for item in practice.criteria],
    )
    blocked = await post(
        client,
        stage_path(person, StageKey.PRACTICE, "observe"),
        DemoRole.MENTOR,
        observation,
    )
    assert_error(blocked, 409, "employer_blocker")
    assert (await bootstrap(client)).revision == state.revision
    resolve_path = f"/api/employees/{person.id}/blocker/resolve"
    command = CommentInput(
        expected_revision=state.revision,
        comment="Доступ выдан, учебная касса проверена вместе с наставником.",
    )
    wrong_role = await post(client, resolve_path, DemoRole.MENTOR, command)
    assert_error(wrong_role, 403, "role_forbidden")
    state = await success(client, resolve_path, DemoRole.MANAGER, command)
    assert employee(state, "seed-mila").blocker is None
    assert state.metrics.blocked_employees == 0
    repeated = await post(
        client,
        resolve_path,
        DemoRole.MANAGER,
        CommentInput(expected_revision=state.revision, comment=COMMENT),
    )
    assert_error(repeated, 409, "invalid_transition")
    observation.expected_revision = state.revision
    state = await success(
        client,
        stage_path(person, StageKey.PRACTICE, "observe"),
        DemoRole.MENTOR,
        observation,
    )
    assert (
        stage(employee(state, "seed-mila"), StageKey.INDEPENDENT).status
        is StageStatus.AVAILABLE
    )
