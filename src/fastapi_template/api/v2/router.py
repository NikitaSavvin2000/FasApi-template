"""Сборка модулей маршрутов второй версии API."""

from fastapi import APIRouter

from fastapi_template.api.v2.routes.examples import router as examples_router

router = APIRouter(tags=["examples-v2"])
router.include_router(examples_router, prefix="/examples")
