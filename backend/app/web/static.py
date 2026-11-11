"""Раздай собранный интерфейс с безопасным SPA fallback отдельно от API."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from starlette.responses import FileResponse


def register_static(app: FastAPI, directory: Path) -> None:
    """Зарегистрируй fallback после всех API-роутеров.

    Args:
        app: приложение FastAPI.
        directory: каталог готовой сборки с index.html.
    """
    root = directory.resolve()
    if not (root / "index.html").is_file():
        message = "В STATIC_DIR отсутствует собранный index.html"
        raise ValueError(message)

    @app.api_route(
        "/{requested_path:path}", methods=["GET", "HEAD"], include_in_schema=False
    )
    async def frontend(requested_path: str) -> FileResponse:
        """Верни файл либо страницу интерфейса для клиентского маршрута.

        Args:
            requested_path: путь относительно корня сайта.

        Returns:
            Безопасно выбранный статический файл.
        """
        target = _resolve_static(root, requested_path)
        return FileResponse(target, headers={"X-Content-Type-Options": "nosniff"})


def _resolve_static(root: Path, requested: str) -> Path:
    """Не маскируй API, отсутствующие ресурсы и выход за пределы каталога.

    Args:
        root: разрешённый каталог собранного интерфейса.
        requested: относительный путь посетителя.

    Returns:
        Файл либо корневой index.html.
    """
    if requested == "api" or requested.startswith("api/"):
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    target = (root / requested).resolve()
    if not target.is_relative_to(root):
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return _file_or_index(root, target)


def _file_or_index(root: Path, target: Path) -> Path:
    """Разреши SPA fallback только для путей без расширения ресурса.

    Args:
        root: каталог интерфейса.
        target: проверенный путь внутри него.

    Returns:
        Существующий ресурс либо index.html.
    """
    if target.is_file():
        return target
    if target.suffix:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return root / "index.html"
