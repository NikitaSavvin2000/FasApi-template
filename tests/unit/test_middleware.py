from __future__ import annotations

import asyncio
from typing import Any

from fastapi_template.core.middleware import BodySizeLimitMiddleware, RequestIdMiddleware


def test_body_limit_rejects_chunked_input_without_content_length() -> None:
    """Лимит тела должен защищать запросы, которым нельзя доверять Content-Length."""

    sent: list[dict[str, Any]] = []

    async def downstream(scope: dict[str, Any], receive: Any, send: Any) -> None:
        raise AssertionError("oversized request must not reach the application")

    messages = iter(
        [
            {"type": "http.request", "body": b"a", "more_body": True},
            {"type": "http.request", "body": b"bc", "more_body": False},
        ]
    )

    async def receive() -> dict[str, Any]:
        return next(messages)

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    asyncio.run(
        BodySizeLimitMiddleware(downstream, max_body_bytes=2)(
            {"type": "http", "headers": []}, receive, send
        )
    )
    assert sent[0]["status"] == 413


def test_request_id_uses_safe_header_and_generates_a_replacement() -> None:
    """Небезопасный входной идентификатор должен заменяться безопасным значением."""

    sent: list[dict[str, Any]] = []

    async def downstream(scope: dict[str, Any], receive: Any, send: Any) -> None:
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    asyncio.run(
        RequestIdMiddleware(downstream)(
            {"type": "http", "headers": [(b"x-request-id", b"unsafe space")]}, receive, send
        )
    )
    header_values = dict(sent[0]["headers"])
    assert header_values[b"x-request-id"] != b"unsafe space"
