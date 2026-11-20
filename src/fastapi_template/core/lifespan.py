"""Настройка жизненного цикла приложения и корректное освобождение ресурсов."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, cast

from anyio import to_thread
from fastapi import FastAPI

from fastapi_template.db.database import initialize_local_database, resolve_database_target

if TYPE_CHECKING:
    from fastapi_template.configs.config import Settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Настраивает лимит потоков и признаки готовности на время жизни приложения."""

    settings: Settings = app.state.settings
    limiter = to_thread.current_default_thread_limiter()
    original_tokens = limiter.total_tokens
    limiter.total_tokens = settings.server.thread_pool_tokens
    version_apps = cast(dict[str, FastAPI], app.state.version_apps)
    try:
        database_target = resolve_database_target(
            settings.database, local_development=settings.local_development
        )
        if database_target.source == "local":
            initialize_local_database(database_target)
        app.state.database_target = database_target
        app.state.ready = True
        app.state.resources_closed = False
        for version_app in version_apps.values():
            version_app.state.database_target = database_target
            version_app.state.ready = True
            version_app.state.resources_closed = False
        yield
    finally:
        app.state.ready = False
        limiter.total_tokens = original_tokens
        app.state.resources_closed = True
        for version_app in version_apps.values():
            version_app.state.ready = False
            version_app.state.resources_closed = True
