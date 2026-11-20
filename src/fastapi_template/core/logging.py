"""Настройка логирования и идентификаторы корреляции запросов."""

from __future__ import annotations

import logging
from contextvars import ContextVar

from fastapi_template.configs.config import LoggingSettings

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)


def configure_logging(settings: LoggingSettings) -> None:
    """Настраивает единый вывод логов согласно валидированным настройкам."""

    logging.basicConfig(
        level=settings.level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        """Добавляет идентификатор запроса в запись лога, если он доступен."""

        record.request_id = request_id_context.get() or "-"
        return True


def install_request_id_filter() -> None:
    """Подключает фильтр request ID к корневому logger без дублирования."""

    root = logging.getLogger()
    if not any(isinstance(existing, RequestIdFilter) for existing in root.filters):
        root.addFilter(RequestIdFilter())
