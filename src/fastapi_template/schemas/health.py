"""Pydantic-схемы служебных маршрутов."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Статус работоспособности или готовности приложения."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "ready"] = Field(
        description="Текущий служебный статус приложения.", examples=["ready"]
    )
