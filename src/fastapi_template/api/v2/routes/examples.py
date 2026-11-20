"""Демонстрационные обработчики второй версии API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends

from fastapi_template.api.dependencies import Processor, get_v2_processor
from fastapi_template.core.errors import ErrorResponse
from fastapi_template.schemas.examples import ProcessRequest, ProcessResponse

router = APIRouter()


@router.post(
    "/process",
    response_model=ProcessResponse,
    operation_id="process_example_v2",
    summary="Повторяет текст в верхнем регистре.",
    description="Передаёт проверенный текст в общий сервис с правилом второй версии API.",
    response_description="Текст успешно обработан во второй версии API.",
    responses={
        200: {
            "content": {
                "application/json": {
                    "examples": {
                        "result": {
                            "summary": "Текст в верхнем регистре повторён два раза",
                            "value": {
                                "result": "ПРИВЕТ, ШАБЛОН ПРИВЕТ, ШАБЛОН",
                                "repetitions": 2,
                                "version": "v2",
                            },
                        }
                    }
                }
            }
        },
        413: {"model": ErrorResponse, "description": "Размер тела запроса превышен."},
    },
)
async def process(
    payload: Annotated[
        ProcessRequest,
        Body(
            description="Параметры обработки текста.",
            openapi_examples={
                "uppercase-repeat": {
                    "summary": "Вторая версия переводит текст в верхний регистр",
                    "value": {"text": "Привет, шаблон", "repetitions": 2},
                }
            },
        ),
    ],
    processor: Annotated[Processor, Depends(get_v2_processor)],
) -> ProcessResponse:
    """Обрабатывает текст сервисом второй версии API."""

    result = processor(payload.text, payload.repetitions)
    return ProcessResponse(result=result.value, repetitions=result.repetitions, version="v2")
