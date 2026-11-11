"""Выдай ресурсы и отдельный UnitOfWork на каждый запрос."""

from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request

from app.core.db import UnitOfWork

from .runtime import Runtime


def get_runtime(request: Request) -> Runtime:
    """Прочитай ресурс, созданный только composition root.

    Args:
        request: текущий запрос FastAPI.

    Returns:
        Типизированные ресурсы запущенного приложения.
    """
    return cast(Runtime, request.app.state.runtime)


RuntimeDep = Annotated[Runtime, Depends(get_runtime)]


async def get_uow(runtime: RuntimeDep) -> AsyncIterator[UnitOfWork]:
    """Закрой сессию и откати незавершённую работу при любом исходе.

    Args:
        runtime: ресурсы текущего приложения.

    Yields:
        Единица работы, которую сценарий фиксирует явно.
    """
    async with runtime.database.unit_of_work() as uow:
        yield uow


UowDep = Annotated[UnitOfWork, Depends(get_uow)]
