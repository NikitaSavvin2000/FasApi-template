"""Небольшие ASGI middleware, не буферизующие потоковые ответы."""

from __future__ import annotations

import re
import uuid

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from fastapi_template.core.logging import request_id_context

_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


class RequestIdMiddleware:
    """Добавляет безопасный идентификатор корреляции, не меняя поток тела ответа."""

    def __init__(self, app: ASGIApp) -> None:
        """Сохраняет вложенное ASGI-приложение."""

        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Добавляет или генерирует request ID для HTTP-ответа."""

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope["headers"]}
        supplied = headers.get(b"x-request-id", b"").decode("ascii", errors="ignore")
        request_id = supplied if _REQUEST_ID.fullmatch(supplied) else str(uuid.uuid4())
        token = request_id_context.set(request_id)

        async def send_with_request_id(message: Message) -> None:
            """Добавляет заголовок request ID непосредственно перед стартом ответа."""

            if message["type"] == "http.response.start":
                response_headers = list(message.get("headers", []))
                response_headers.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = response_headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            request_id_context.reset(token)


class BodySizeLimitMiddleware:
    """Отклоняет большие тела запросов, сохраняя потоковую выдачу нижележащего слоя."""

    def __init__(self, app: ASGIApp, max_body_bytes: int) -> None:
        """Сохраняет вложенное приложение и максимальный размер тела запроса."""

        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Буферизует ограниченное тело запроса и отклоняет превышение лимита."""

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope["headers"]}
        raw_length = headers.get(b"content-length")
        if raw_length is not None:
            try:
                if int(raw_length) > self.max_body_bytes:
                    await self._send_error(send)
                    return
            except ValueError:
                await self._send_error(send)
                return

        body_parts: list[bytes] = []
        consumed = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            chunk = message.get("body", b"")
            consumed += len(chunk)
            if consumed > self.max_body_bytes:
                # Reading only up to the limit avoids trusting a missing or
                # malicious Content-Length while keeping an error response
                # under our control before FastAPI parses the body.
                await self._send_error(send)
                return
            body_parts.append(chunk)
            if not message.get("more_body", False):
                break

        body = b"".join(body_parts)
        delivered = False

        async def replay_receive() -> Message:
            """Повторно отдаёт проверенное тело и сохраняет канал отключения клиента."""

            nonlocal delivered
            if delivered:
                # Streaming handlers may poll ``is_disconnected`` after the
                # request body has been replayed. Delegate those polls to the
                # original receive channel instead of inventing a disconnect.
                return await receive()
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay_receive, send)

    async def _send_error(self, send: Send) -> None:
        """Отправляет безопасный ответ 413 без передачи запроса вложенному приложению."""

        response = JSONResponse(
            {"detail": "Request body exceeds the configured size limit."}, status_code=413
        )
        await send(
            {
                "type": "http.response.start",
                "status": response.status_code,
                "headers": list(response.raw_headers),
            }
        )
        await send({"type": "http.response.body", "body": response.body})
