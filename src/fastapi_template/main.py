"""Фабрика приложения FastAPI; импорт модуля не имеет побочных эффектов."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from fastapi_template.api.router import build_version_router
from fastapi_template.configs.config import Settings, load_settings
from fastapi_template.core.lifespan import lifespan
from fastapi_template.core.middleware import BodySizeLimitMiddleware, RequestIdMiddleware
from fastapi_template.core.version import API_PREFIXES, PROJECT_VERSION


def _install_validation_error_handler(app: FastAPI) -> None:
    """Добавляет единый безопасный ответ на ошибки валидации в приложение."""

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, error: RequestValidationError) -> JSONResponse:
        """Возвращает расположение и сообщение ошибки без отклонённых значений."""

        details: list[dict[str, Any]] = []
        for item in error.errors():
            details.append({key: item[key] for key in ("type", "loc", "msg")})
        return JSONResponse(status_code=422, content={"detail": details})


def _create_version_app(settings: Settings, version: Literal["v1", "v2"]) -> FastAPI:
    """Создаёт изолированное приложение одной публичной версии API."""

    docs_url = "/docs" if settings.docs.enabled else None
    redoc_url = "/redoc" if settings.docs.enabled else None
    openapi_url = "/openapi.json" if settings.docs.enabled else None
    app = FastAPI(
        title=f"API шаблона FastAPI — {version}",
        version=PROJECT_VERSION,
        description=(
            f"Документация и маршруты версии {version} API. "
            "Другие версии намеренно не включены в этот контракт."
        ),
        openapi_version="3.1.0",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )
    app.state.settings = settings
    app.state.ready = False
    app.state.resources_closed = False
    _install_validation_error_handler(app)
    app.include_router(build_version_router(version))
    return app


def create_app(settings: Settings | None = None) -> FastAPI:
    """Создаёт независимый экземпляр приложения с необязательными настройками теста."""

    active_settings = settings or load_settings()
    app = FastAPI(
        title="Маршрутизатор API шаблона FastAPI",
        version=PROJECT_VERSION,
        description="Корневое приложение маршрутизирует запросы в независимые версии API.",
        openapi_version="3.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.settings = active_settings
    app.state.ready = False
    app.state.resources_closed = False

    # Middleware работает с ASGI-сообщениями и не собирает потоковый ответ в память.
    app.add_middleware(
        BodySizeLimitMiddleware, max_body_bytes=active_settings.request.max_body_bytes
    )
    app.add_middleware(RequestIdMiddleware)
    if active_settings.trusted_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=active_settings.trusted_hosts)
    if active_settings.cors.enabled:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=active_settings.cors.allow_origins,
            allow_credentials=active_settings.cors.allow_credentials,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-Request-ID"],
        )

    versions: tuple[Literal["v1", "v2"], ...] = ("v1", "v2")
    if len(API_PREFIXES) != len(versions) or len(set(API_PREFIXES)) != len(API_PREFIXES):
        raise RuntimeError("Для каждой версии API нужен уникальный URL-префикс")
    version_apps = {version: _create_version_app(active_settings, version) for version in versions}
    app.state.version_apps = version_apps
    for prefix, version in zip(API_PREFIXES, versions, strict=True):
        app.mount(prefix, version_apps[version])
    return app
