"""Pydantic-схемы демонстрационных маршрутов API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProcessRequest(BaseModel):
    """Входные данные для детерминированной обработки текста."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(
        min_length=1,
        max_length=1_000,
        description="Текст для обработки длиной от 1 до 1000 символов.",
        examples=["Привет, шаблон"],
    )
    repetitions: int = Field(
        ge=1,
        le=10,
        description="Количество повторений текста от 1 до 10.",
        examples=[2],
    )


class ProcessResponse(BaseModel):
    """Результат синхронной обработки текста."""

    model_config = ConfigDict(extra="forbid")

    result: str = Field(
        min_length=1,
        max_length=10_000,
        description="Детерминированный текстовый результат обработки.",
        examples=["Привет, шаблон Привет, шаблон"],
    )
    repetitions: int = Field(
        ge=1,
        le=10,
        description="Количество повторений, применённое сервисом.",
        examples=[2],
    )
    version: Literal["v1", "v2"] = Field(
        description="Версия API, сформировавшая ответ.", examples=["v1"]
    )
