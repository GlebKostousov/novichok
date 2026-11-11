"""Настрой структурные логи без тел запросов и секретов."""

import structlog


def configure_logging(*, json_output: bool) -> None:
    """Выбери формат логов в точке сборки приложения.

    Args:
        json_output: включить машинно читаемый JSON.
    """
    renderer = (
        structlog.processors.JSONRenderer(ensure_ascii=False)
        if json_output
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Верни логгер модуля со стабильным именем.

    Args:
        name: имя вызывающего модуля.

    Returns:
        Связанный структурный логгер.
    """
    return structlog.stdlib.get_logger(name)
