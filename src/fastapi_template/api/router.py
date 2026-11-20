"""Сборка маршрутов отдельного versioned FastAPI-приложения."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request

from fastapi_template.api.v1.router import router as v1_router
from fastapi_template.api.v2.router import router as v2_router
from fastapi_template.schemas.health import HealthResponse


def build_version_router(version: Literal["v1", "v2"]) -> APIRouter:
    """Создаёт router версии с её служебными и прикладными маршрутами."""

    router = APIRouter()

    @router.get(
        "/health/live",
        response_model=HealthResponse,
        operation_id=f"health_live_{version}",
        tags=["health"],
        summary="Проверка работоспособности процесса.",
        description="Возвращает успешный ответ, если процесс приложения работает.",
        response_description="Процесс работает.",
        responses={
            200: {
                "content": {"application/json": {"examples": {"live": {"value": {"status": "ok"}}}}}
            }
        },
    )
    async def live() -> HealthResponse:
        """Возвращает статус работающего процесса."""

        return HealthResponse(status="ok")

    @router.get(
        "/health/ready",
        response_model=HealthResponse,
        operation_id=f"health_ready_{version}",
        tags=["health"],
        summary="Проверка готовности приложения.",
        description="Показывает, что жизненный цикл приложения подготовил его ресурсы.",
        response_description="Приложение готово обслуживать запросы.",
        responses={
            200: {
                "content": {
                    "application/json": {"examples": {"ready": {"value": {"status": "ready"}}}}
                }
            }
        },
    )
    async def ready(request: Request) -> HealthResponse:
        """Возвращает статус готовности ресурсов приложения."""

        return HealthResponse(status="ready" if request.app.state.ready else "ok")

    if version == "v1":
        router.include_router(v1_router)
    else:
        router.include_router(v2_router)
    return router
