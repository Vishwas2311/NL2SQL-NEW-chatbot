"""FastAPI transport, lifecycle, safe errors and thin EWS compatibility mappings."""

import json
import logging
import secrets
import sqlite3
import time
from collections import deque
from collections.abc import AsyncGenerator, Callable
from contextlib import ExitStack, asynccontextmanager, closing
from dataclasses import dataclass
from threading import Lock
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import Field
from starlette.middleware.base import RequestResponseEndpoint

from nl2sql.auth import Authenticator
from nl2sql.catalog import CatalogStore
from nl2sql.compatibility import error_payload
from nl2sql.config import Settings
from nl2sql.database import SQLiteDatabase
from nl2sql.domain import Answer, Failure, FrozenModel, Principal, Row
from nl2sql.embeddings import ManagedEncoder, build_embedding
from nl2sql.managed_resources import build_managed_resources
from nl2sql.middleware import BodyLimitMiddleware
from nl2sql.model import ModelProvider, build_model
from nl2sql.planning import principal_hash
from nl2sql.ports import ApplicationResources
from nl2sql.retrieval import EmbeddingProvider, Retriever
from nl2sql.security import SQLValidator
from nl2sql.service import ChatService
from nl2sql.sessions import SessionStore, SessionSummary
from nl2sql.telemetry import REQUEST_ID

LOGGER = logging.getLogger("nl2sql")


class ChatRequest(FrozenModel):
    """Existing EWS body; user_id is only a consistency assertion."""

    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=100)
    user_id: str | None = Field(default=None, max_length=100)


class EWSResponse(FrozenModel):
    """Stable keys consumed by the immutable JavaScript reference."""

    session_id: str
    response: str
    results: tuple[Row, ...]
    status: str
    metadata: dict[str, object] | None = None


class SessionList(FrozenModel):
    """Bounded legacy-compatible session list."""

    sessions: tuple[SessionSummary, ...]


class DisplayMessage(FrozenModel):
    """Public history contains safe rows without internal policy details."""

    role: str
    content: str
    timestamp: str
    results: tuple[Row, ...]


class SessionHistory(FrozenModel):
    """Owned message collection consumed by the existing UI."""

    messages: tuple[DisplayMessage, ...]


@dataclass
class Resources:
    """Singleton resources shared by application use cases, closed at shutdown."""

    auth: Authenticator
    sessions: SessionStore
    database: SQLiteDatabase
    retriever: Retriever
    model: ModelProvider
    service: ChatService
    encoder: ManagedEncoder | None = None

    def close(self) -> None:
        """Release initialized resources in reverse dependency order."""
        self.model.close()
        self.retriever.close()
        if self.encoder is not None:
            self.encoder.close()
        self.database.close()
        self.sessions.close()

    def components(self) -> dict[str, str]:
        """Configuration and local compatibility signals, without probing external inference."""
        return {
            "metadata": "pinned_catalog",
            "index": "compatible",
            "model": "disabled"
            if self.service.settings.model_mode == "disabled"
            else "configured_unprobed",
            "embedding": "disabled" if self.retriever.encoder is None else "configured_unprobed",
        }


def build_resources(
    settings: Settings,
    model: ModelProvider | None = None,
    encoder: EmbeddingProvider | None = None,
) -> Resources:
    """No implicit seeding, model downloads, Oracle connections or metadata crawling."""
    if settings.query_backend != "sqlite":
        raise ValueError("Oracle query execution requires a governed metadata root")
    auth = Authenticator(settings)
    if (
        not settings.catalog_digest
        or not settings.principals
        or not (settings.tokens or settings.jwt_secret)
    ):
        raise ValueError("Initialize synthetic data and secure authentication before startup")
    store = CatalogStore(settings.catalog_path, settings.catalog_digest)
    with closing(
        sqlite3.connect(
            (settings.data_dir / "banking.db").resolve().as_uri() + "?mode=ro", uri=True
        )
    ) as conn:
        catalog = store.load(conn)
    validator = SQLValidator(catalog, secrets.token_bytes(32))
    with ExitStack() as cleanup:
        database = SQLiteDatabase(settings.data_dir / "banking.db", validator, settings)
        cleanup.callback(database.close)
        configured_encoder = build_embedding(settings) if encoder is None else None
        if configured_encoder is not None:
            cleanup.callback(configured_encoder.close)
        retriever = Retriever(
            catalog,
            settings.principals,
            encoder or configured_encoder,
            options=settings.retrieval_options,
        )
        cleanup.callback(retriever.close)
        sessions = SessionStore(settings.data_dir / "sessions.db", settings.session_retention_days)
        cleanup.callback(sessions.close)
        provider = model or build_model(settings)
        cleanup.callback(provider.close)
        service = ChatService(settings, store, retriever, provider, database, sessions)
        cleanup.pop_all()
    return Resources(auth, sessions, database, retriever, provider, service, configured_encoder)


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
    settings: Settings | None = None,
    model: ModelProvider | None = None,
    resources_factory: Callable[[Settings, ModelProvider | None], ApplicationResources]
    | None = None,
) -> FastAPI:
    """Build transport without allocating expensive resources until application startup."""
    configuration = settings or Settings()
    resources: ApplicationResources | None = None
    rate_lock = Lock()
    windows: dict[str, deque[float]] = {}

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        nonlocal resources
        factory = resources_factory or (
            build_managed_resources if configuration.metadata_root is not None else build_resources
        )
        try:
            resources = factory(configuration, model)
        except (Failure, ValueError, OSError, sqlite3.Error, ImportError) as error:
            code = (
                error.code
                if isinstance(error, Failure)
                else (
                    "OPTIONAL_DEPENDENCY"
                    if isinstance(error, ImportError)
                    else "STARTUP_CONFIGURATION"
                )
            )
            raise Failure(
                code, "Backend startup checks failed; review sanitized diagnostics.", 503
            ) from None
        try:
            yield
        finally:
            resources.close()
            resources = None

    app = FastAPI(
        title="EWS governed NL-to-SQL",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )

    def ready() -> ApplicationResources:
        if resources is None:
            raise Failure("NOT_READY", "The service is not ready.", 503)
        return resources

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
        with rate_lock:
            window = windows.setdefault(identity.id, deque())
            now = time.monotonic()
            while window and window[0] <= now - 60:
                window.popleft()
            if len(window) >= configuration.requests_per_minute:
                raise Failure("RATE_LIMIT", "Too many requests; please try again shortly.", 429)
            window.append(now)
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
            error_payload(request.url.path, error.code, error.message), status_code=error.status
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

    @app.exception_handler(sqlite3.Error)
    async def storage_handler(request: Request, _error: sqlite3.Error) -> JSONResponse:
        return JSONResponse(
            error_payload(
                request.url.path, "STORAGE_UNAVAILABLE", "Local storage is temporarily unavailable."
            ),
            status_code=503,
        )

    @app.get("/health")
    @app.get("/api/v1/health/live")
    def health() -> dict[str, str]:
        return {"status": "healthy"}

    @app.get("/api/v1/health/ready")
    def readiness() -> dict[str, str]:
        active = ready()
        active.database.ready()
        return {"status": "healthy"}

    @app.get("/api/v1/health/components")
    def components(_identity: Annotated[Principal, Depends(principal)]) -> dict[str, str]:
        active = ready()
        active.database.ready()
        return {"process": "alive", "database": "available", **active.components()}

    @app.post("/ews-chatbot/chat", response_model=EWSResponse)
    def chat(body: ChatRequest, identity: Annotated[Principal, Depends(principal)]) -> EWSResponse:
        spans: dict[str, float] = {"model_calls": 0}
        answer = ready().service.chat(body.message, body.session_id, identity, body.user_id, spans)
        LOGGER.info(
            json.dumps(
                {
                    "event": "pipeline",
                    "request_id": REQUEST_ID.get(),
                    "status": answer.status,
                    "spans": spans,
                }
            )
        )
        return to_ews(answer)

    @app.post("/api/v1/chat", response_model=Answer)
    def typed_chat(body: ChatRequest, identity: Annotated[Principal, Depends(principal)]) -> Answer:
        return ready().service.chat(body.message, body.session_id, identity, body.user_id, {})

    @app.get("/ews-chatbot/get_all_sessions", response_model=SessionList)
    @app.get("/api/v1/sessions", response_model=SessionList)
    def sessions(identity: Annotated[Principal, Depends(principal)]) -> SessionList:
        return SessionList(sessions=ready().sessions.list_owned(identity.id))

    @app.get("/ews-chatbot/load_session/{session_id}", response_model=SessionHistory)
    @app.get("/api/v1/sessions/{session_id}", response_model=SessionHistory)
    def history(
        session_id: str, identity: Annotated[Principal, Depends(principal)]
    ) -> SessionHistory:
        saved = ready().sessions.messages(session_id, identity.id, principal_hash(identity))
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
        ready().sessions.delete(session_id, identity.id)
        return Response(status_code=204)

    @app.post("/api/v1/speech/transcriptions")
    def speech(_identity: Annotated[Principal, Depends(principal)]) -> Response:
        raise Failure("SPEECH_DISABLED", "Speech transcription is not enabled.", 501)

    app.add_middleware(BodyLimitMiddleware)
    return app
