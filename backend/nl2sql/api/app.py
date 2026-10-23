"""FastAPI transport, lifecycle, safe errors and thin EWS compatibility mappings."""

import json
import logging
import os
import time
from collections.abc import AsyncGenerator, Callable
from contextlib import ExitStack, asynccontextmanager
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint

from nl2sql.api.compatibility import error_payload, failure_status
from nl2sql.api.middleware import BodyLimitMiddleware
from nl2sql.api.schemas import ChatRequest, DisplayMessage, EWSResponse, SessionHistory, SessionList
from nl2sql.application.ports import ApplicationResources, ModelProvider, RateLimiter
from nl2sql.domain.models import Answer, Failure, Principal
from nl2sql.settings import Settings
from nl2sql.telemetry import REQUEST_ID, STAGE_SPANS, stage_metrics

LOGGER = logging.getLogger("nl2sql")


def to_ews(answer: Answer) -> EWSResponse:
    """Compatibility mapping never introduces SQL text or physical identifiers."""
    return EWSResponse(
        session_id=answer.session_id,
        response=answer.message,
        results=answer.rows,
        status=answer.status,
        metadata=answer.provenance.model_dump(mode="json") if answer.provenance else None,
    )


def create_app(
    configuration: Settings,
    model: ModelProvider | None,
    resources_factory: Callable[[Settings, ModelProvider | None], ApplicationResources],
    rate_limiter_factory: Callable[[Settings], RateLimiter],
) -> FastAPI:
    """Expose HTTP contracts while the composition root supplies infrastructure."""
    resources: ApplicationResources | None = None
    limiter: RateLimiter | None = None

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        nonlocal resources, limiter
        with ExitStack() as cleanup:
            try:
                limiter = rate_limiter_factory(configuration)
                cleanup.callback(limiter.close)
                limiter.ready()
                resources = resources_factory(configuration, model)
                cleanup.callback(resources.close)
            except (Failure, ValueError, OSError, ImportError) as error:
                code = (
                    error.code
                    if isinstance(error, Failure)
                    else "OPTIONAL_DEPENDENCY"
                    if isinstance(error, ImportError)
                    else "STARTUP_CONFIGURATION"
                )
                raise Failure(
                    code,
                    "Backend startup checks failed; review sanitized diagnostics.",
                    "unavailable",
                ) from None
            try:
                yield
            finally:
                resources = None
                limiter = None

    app = FastAPI(
        title="EWS governed NL-to-SQL",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )

    def ready() -> ApplicationResources:
        if resources is None:
            raise Failure("NOT_READY", "The service is not ready.", "unavailable")
        return resources

    def admission() -> RateLimiter:
        if limiter is None:
            raise Failure("NOT_READY", "The service is not ready.", "unavailable")
        return limiter

    def principal(authorization: Annotated[str | None, Header()] = None) -> Principal:
        started = time.perf_counter()
        identity = ready().auth.authenticate(authorization)
        LOGGER.info(
            json.dumps(
                {
                    "event": "authentication",
                    "request_id": REQUEST_ID.get(),
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                }
            )
        )
        admission().check(identity)
        return identity

    @app.middleware("http")
    async def correlation(request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        try:
            request_id = str(UUID(request.headers.get("X-Request-ID", "")))
        except ValueError:
            request_id = str(uuid4())
        context_token = REQUEST_ID.set(request_id)
        try:
            with stage_metrics({}, time.time() + configuration.request_timeout_seconds):
                response = await call_next(request)
        finally:
            REQUEST_ID.reset(context_token)
        response.headers["X-Request-ID"] = request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        LOGGER.info(
            json.dumps(
                {
                    "event": "http_request",
                    "worker_pid": os.getpid(),
                    "request_id": request_id,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                }
            )
        )
        return response

    @app.exception_handler(Failure)
    async def failure_handler(request: Request, error: Failure) -> JSONResponse:
        return JSONResponse(
            error_payload(request.url.path, error.code, error.message),
            status_code=failure_status(error),
            headers={"Retry-After": "1"} if error.kind == "busy" else None,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, _error: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            error_payload(request.url.path, "INVALID_REQUEST", "Invalid request fields."),
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def unexpected_handler(request: Request, error: Exception) -> JSONResponse:
        LOGGER.error(json.dumps({"event": "unhandled_failure", "type": type(error).__name__}))
        return JSONResponse(
            error_payload(
                request.url.path, "INTERNAL_ERROR", "The request could not be completed."
            ),
            status_code=500,
        )

    @app.get("/health")
    @app.get("/api/v1/health/live")
    def health() -> dict[str, str]:
        return {"status": "healthy"}

    @app.get("/api/v1/health/ready")
    def readiness() -> dict[str, str]:
        active = ready()
        active.database.ready()
        admission().ready()
        return {"status": "healthy"}

    @app.get("/api/v1/health/components")
    def components(_identity: Annotated[Principal, Depends(principal)]) -> dict[str, str]:
        active = ready()
        active.database.ready()
        admission().ready()
        return {
            "process": "alive",
            "database": "available",
            "rate_limiter": admission().backend,
            **active.components(),
        }

    def invoke_chat(body: ChatRequest, identity: Principal) -> Answer:
        spans = STAGE_SPANS.get()
        if spans is None:
            spans = {}
        spans.setdefault("model_calls", 0)
        status = "failed"
        code: str | None = None
        try:
            with admission().chat(identity):
                answer = ready().service.chat(
                    body.message, body.session_id, identity, body.user_id, spans
                )
            status = answer.status
            return answer
        except Failure as error:
            code = error.code
            raise
        finally:
            LOGGER.info(
                json.dumps(
                    {
                        "event": "pipeline",
                        "request_id": REQUEST_ID.get(),
                        "status": status,
                        "error_code": code,
                        "spans": spans,
                    }
                )
            )

    @app.post("/ews-chatbot/chat", response_model=EWSResponse)
    def chat(body: ChatRequest, identity: Annotated[Principal, Depends(principal)]) -> EWSResponse:
        return to_ews(invoke_chat(body, identity))

    @app.post("/api/v1/chat", response_model=Answer)
    def typed_chat(body: ChatRequest, identity: Annotated[Principal, Depends(principal)]) -> Answer:
        return invoke_chat(body, identity)

    @app.get("/ews-chatbot/get_all_sessions", response_model=SessionList)
    @app.get("/api/v1/sessions", response_model=SessionList)
    def sessions(identity: Annotated[Principal, Depends(principal)]) -> SessionList:
        return SessionList(sessions=ready().conversations.list_owned(identity))

    @app.get("/ews-chatbot/load_session/{session_id}", response_model=SessionHistory)
    @app.get("/api/v1/sessions/{session_id}", response_model=SessionHistory)
    def history(
        session_id: str, identity: Annotated[Principal, Depends(principal)]
    ) -> SessionHistory:
        saved = ready().conversations.messages(session_id, identity)
        return SessionHistory(
            messages=tuple(
                DisplayMessage(
                    role=item.role,
                    content=item.content,
                    timestamp=item.timestamp,
                    results=item.results,
                )
                for item in saved
            )
        )

    @app.delete("/ews-chatbot/delete_session/{session_id}", status_code=204)
    @app.delete("/api/v1/sessions/{session_id}", status_code=204)
    def delete(session_id: str, identity: Annotated[Principal, Depends(principal)]) -> Response:
        ready().conversations.delete(session_id, identity)
        return Response(status_code=204)

    @app.post("/api/v1/speech/transcriptions")
    def speech(_identity: Annotated[Principal, Depends(principal)]) -> Response:
        raise Failure("SPEECH_DISABLED", "Speech transcription is not enabled.", "not_implemented")

    app.add_middleware(BodyLimitMiddleware)
    return app
