"""Existing API resources with an opt-in governed metadata runtime."""

from contextlib import ExitStack
from dataclasses import dataclass

from nl2sql.application.metadata.workflow import MetadataWorkflow
from nl2sql.application.ports import ModelProvider
from nl2sql.application.sessions import SessionService
from nl2sql.bootstrap.runtime import BundleChatService, RuntimeFactory, RuntimeManager
from nl2sql.domain.models import Failure
from nl2sql.infrastructure.auth import Authenticator
from nl2sql.infrastructure.inference.model import build_model
from nl2sql.infrastructure.metadata.builder import BundleBuilder
from nl2sql.infrastructure.metadata.config import authority_from_environment, load_profile
from nl2sql.infrastructure.metadata.store import MetadataRepository
from nl2sql.infrastructure.rate_limit import build_inference_admission
from nl2sql.infrastructure.retrieval.embeddings import build_embedding
from nl2sql.infrastructure.sessions import SessionStore
from nl2sql.settings import Settings


class ManagedReadiness:
    """Health checking pins one data adapter, just like a chat request."""

    def __init__(self, manager: RuntimeManager) -> None:
        self.manager = manager

    def ready(self) -> None:
        """Check the currently published data adapter."""
        with self.manager.pin() as bundle:
            bundle.service.model.admission.ready()
            bundle.database.ready()


@dataclass
class ManagedResources:
    """Sessions/auth/model are shared; old metadata pools drain independently."""

    auth: Authenticator
    sessions: SessionStore
    database: ManagedReadiness
    service: BundleChatService
    manager: RuntimeManager

    @property
    def conversations(self) -> SessionService:
        """The identity adapter refreshes governed grants before protected responses."""
        return SessionService(self.sessions, self.auth)

    def close(self) -> None:
        """The manager defers shared cleanup until its final request lease releases."""
        self.manager.close()

    def components(self) -> dict[str, str]:
        """A verified publication is pinned while checking compatibility/configuration."""
        with self.manager.pin() as bundle:
            return {
                "metadata": "published",
                "index": "compatible",
                "bundle_version": bundle.version,
                "model": "disabled"
                if bundle.service.settings.model_mode == "disabled"
                else "configured_unprobed",
                "embedding": "disabled"
                if bundle.retriever.encoder is None
                else "configured_unprobed",
            }


def build_managed_resources(
    settings: Settings, model: ModelProvider | None = None
) -> ManagedResources:
    """No periodic Oracle poller is ever started by a FastAPI worker."""
    if settings.metadata_root is None:
        raise ValueError("A private metadata repository must be configured")
    profile = load_profile(settings.metadata_root)
    authority = authority_from_environment()
    if authority is None:
        raise Failure(
            "ADMIN_CONFIGURATION",
            "Metadata verification trust anchors are required.",
            "unavailable",
        )
    with ExitStack() as cleanup:
        repository = MetadataRepository(settings.metadata_root)
        cleanup.callback(repository.close)
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
        encoder = build_embedding(settings)
        if encoder is not None:
            cleanup.callback(encoder.close)
        version = encoder.identity if encoder else None
        factory = RuntimeFactory(
            settings, sessions, provider, encoder, version, inference_admission=inference
        )
        workflow = MetadataWorkflow(
            repository,
            profile.provider(),
            authority,
            builder=BundleBuilder(
                encoder,
                version,
                retrieval_options=settings.retrieval_options,
                native_dir=settings.graph_native_dir,
            ),
            runtime_check=factory.check,
        )
        active = repository.control().active
        if active is None:
            raise Failure(
                "NO_ACTIVE_METADATA",
                "Review and publish a bundle before starting the backend.",
                "unavailable",
            )
        workflow.verify_record(repository.get(active))
        # Approved snapshots load without discovery; a deployment can require a startup gate.
        if settings.metadata_startup_reconcile:
            workflow.stage()
        auth = Authenticator(settings)

        def close_shared() -> None:
            with ExitStack() as closing:
                closing.callback(repository.close)
                closing.callback(sessions.close)
                closing.callback(inference.close)
                if encoder is not None:
                    closing.callback(encoder.close)
                closing.callback(provider.close)

        manager = RuntimeManager(workflow, factory, auth.replace_principals, close_shared)
        auth.refresh_hook = manager.reload
        cleanup.pop_all()
    return ManagedResources(
        auth, sessions, ManagedReadiness(manager), BundleChatService(manager), manager
    )
