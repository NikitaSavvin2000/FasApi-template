"""Заменяемые HTTP-зависимости."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from fastapi import Request

from fastapi_template.configs.config import Settings
from fastapi_template.db.database import DatabaseTarget
from fastapi_template.models.examples import ProcessedText
from fastapi_template.services.examples import process_text

Processor = Callable[[str, int], ProcessedText]


def get_settings(request: Request) -> Settings:
    """Возвращает настройки, привязанные к текущему экземпляру приложения."""

    return cast(Settings, request.app.state.settings)


def get_database_target(request: Request) -> DatabaseTarget:
    """Возвращает выбранный жизненным циклом источник данных текущей версии API."""

    return cast(DatabaseTarget, request.app.state.database_target)


def get_v1_processor() -> Processor:
    """Возвращает обработчик текста с правилами первой версии API."""

    return lambda text, repetitions: process_text(text, repetitions)


def get_v2_processor() -> Processor:
    """Возвращает обработчик текста с правилами второй версии API."""

    return lambda text, repetitions: process_text(text, repetitions, uppercase=True)
