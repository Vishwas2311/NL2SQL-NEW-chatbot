"""ASGI request budget enforcement without reading an unbounded body."""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from nl2sql.compatibility import error_payload


class BodyLimitMiddleware:
    """Buffer at most 32KB before invoking JSON parsing or any authenticated use case."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            part = message.get("body", b"")
            if len(body) + len(part) > 32_000:
                response = JSONResponse(
                    error_payload(scope["path"], "INPUT_TOO_LARGE", "Request is too large."),
                    status_code=413,
                )
                await response(scope, receive, send)
                return
            body.extend(part)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
