"""Демонстрационные обработчики первой версии API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends

from fastapi_template.api.dependencies import Processor, get_v1_processor
from fastapi_template.core.errors import ErrorResponse
from fastapi_template.schemas.examples import ProcessRequest, ProcessResponse

router = APIRouter()


@router.post(
    "/process",
    response_model=ProcessResponse,
    operation_id="process_example_v1",
    summary="Детерминированно повторяет текст.",
    description="Передаёт проверенный текст в сервис и возвращает результат первой версии API.",
    response_description="Текст успешно обработан.",
    responses={
        200: {
            "content": {
                "application/json": {
                    "examples": {
                        "result": {
                            "summary": "Текст повторён два раза",
                            "value": {
                                "result": "Привет, шаблон Привет, шаблон",
                                "repetitions": 2,
                                "version": "v1",
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
                "repeat": {
                    "summary": "Детерминированное повторение",
                    "value": {"text": "Привет, шаблон", "repetitions": 2},
                }
            },
        ),
    ],
    processor: Annotated[Processor, Depends(get_v1_processor)],
) -> ProcessResponse:
    """Обрабатывает текст сервисом первой версии API."""

    result = processor(payload.text, payload.repetitions)
    return ProcessResponse(result=result.value, repetitions=result.repetitions, version="v1")
