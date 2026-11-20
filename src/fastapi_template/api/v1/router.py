"""Сборка модулей маршрутов первой версии API."""

from fastapi import APIRouter

from fastapi_template.api.v1.routes.examples import router as examples_router

router = APIRouter(tags=["examples-v1"])
router.include_router(examples_router, prefix="/examples")
