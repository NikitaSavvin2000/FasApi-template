"""Точка модульного запуска ``python -m fastapi_template``."""

from __future__ import annotations

import logging

import uvicorn

from fastapi_template.configs.config import Settings, load_settings
from fastapi_template.core.logging import configure_logging, install_request_id_filter
from fastapi_template.core.version import API_PREFIXES


def _display_base_url(settings: Settings) -> str:
    """Возвращает адрес, пригодный для открытия в локальном браузере."""

    if settings.docs.external_base_url:
        return settings.docs.external_base_url.rstrip("/")
    host = "127.0.0.1" if settings.server.host == "0.0.0.0" else settings.server.host
    return f"http://{host}:{settings.server.port}"


def run_server(settings: Settings) -> None:
    """Запускает Uvicorn с валидированными настройками и импортируемой фабрикой."""

    configure_logging(settings.logging)
    install_request_id_filter()
    base_url = _display_base_url(settings)
    logger = logging.getLogger(__name__)
    logger.info("service available at %s", base_url)
    if settings.docs.enabled:
        for prefix in API_PREFIXES:
            logger.info("документация: %s%s/docs и %s%s/redoc", base_url, prefix, base_url, prefix)
    uvicorn.run(
        "fastapi_template.main:create_app",
        factory=True,
        host=settings.server.host,
        port=settings.server.port,
        workers=settings.server.workers,
        reload=settings.server.reload,
        log_level=settings.logging.level.lower(),
    )


def main() -> None:
    """Загружает настройки и запускает сервер."""

    run_server(load_settings())


if __name__ == "__main__":
    main()
