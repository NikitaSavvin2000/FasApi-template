"""Публичные схемы ошибок API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    """Безопасное сообщение об ошибке для клиента."""

    model_config = ConfigDict(extra="forbid")

    detail: str = Field(
        description="Безопасное описание причины ошибки без внутренних данных.",
        examples=["Размер тела запроса превышает настроенное ограничение."],
    )
