"""Composition root for the synthetic backend and its owned resources."""

import secrets
import sqlite3
from contextlib import ExitStack, closing
from dataclasses import dataclass

from nl2sql.application.chat import ChatService
from nl2sql.application.inference import InferencePlanner
from nl2sql.application.ports import EmbeddingProvider, ModelProvider, RateLimiter
from nl2sql.application.query.security import SQLValidator
from nl2sql.application.sessions import SessionService
from nl2sql.domain.fingerprints import catalog_hash
from nl2sql.infrastructure.auth import Authenticator
from nl2sql.infrastructure.databases.sqlite import SQLiteDatabase
from nl2sql.infrastructure.graph import SurrealGraph
from nl2sql.infrastructure.inference.model import build_model
from nl2sql.infrastructure.metadata.catalog_store import CatalogStore
from nl2sql.infrastructure.rate_limit import build_inference_admission
from nl2sql.infrastructure.retrieval.embeddings import ManagedEncoder, build_embedding
from nl2sql.infrastructure.retrieval.lexical import Retriever
from nl2sql.infrastructure.sessions import SessionStore
from nl2sql.settings import Settings


@dataclass
class Resources:
    """Singleton resources shared by application use cases, closed at shutdown."""

    auth: Authenticator
    sessions: SessionStore
    database: SQLiteDatabase
    retriever: Retriever
    model: ModelProvider
    service: ChatService
    auxiliary: tuple[SurrealGraph | ManagedEncoder | RateLimiter, ...] = ()

    @property
    def conversations(self) -> SessionService:
        """Compose stateless session use cases over the current owned adapters."""
        return SessionService(self.sessions, self.auth)

    def close(self) -> None:
        """Release initialized resources in reverse dependency order."""
        with ExitStack() as cleanup:
            for resource in (
                self.sessions,
                self.database,
                *self.auxiliary,
                self.retriever,
                self.model,
            ):
                cleanup.callback(resource.close)

    def components(self) -> dict[str, str]:
        """Configuration and local compatibility signals, without probing external inference."""
        self.service.model.admission.ready()
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
    with ExitStack() as cleanup:
        graph = SurrealGraph.build(
            settings.data_dir / "graphs" / (catalog_hash(catalog) + ".surreal.json"),
            catalog,
        )
        cleanup.callback(graph.close)
        validator = SQLValidator(catalog, secrets.token_bytes(32), traversal=graph)
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
        sessions = SessionStore(
            settings.data_dir / "sessions.db",
            settings.session_retention_days,
            settings.max_session_bytes,
        )
        cleanup.callback(sessions.close)
        provider = model or build_model(settings)
        cleanup.callback(provider.close)
        inference = build_inference_admission(settings)
        cleanup.callback(inference.close)
        service = ChatService(
            settings,
            catalog,
            retriever,
            InferencePlanner(provider, inference),
            database,
            sessions,
            sql_validator=validator,
            traversal=graph,
        )
        cleanup.pop_all()
    return Resources(
        auth,
        sessions,
        database,
        retriever,
        provider,
        service,
        (graph, inference, configured_encoder)
        if configured_encoder is not None
        else (graph, inference),
    )
