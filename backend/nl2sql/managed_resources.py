"""Existing API resources with an opt-in governed metadata runtime."""

from contextlib import ExitStack
from dataclasses import dataclass

from nl2sql.auth import Authenticator
from nl2sql.bundle_build import BundleBuilder
from nl2sql.config import Settings
from nl2sql.domain import Failure
from nl2sql.embeddings import build_embedding
from nl2sql.metadata_config import authority_from_environment, load_profile
from nl2sql.metadata_store import MetadataRepository
from nl2sql.metadata_workflow import MetadataWorkflow
from nl2sql.model import ModelProvider, build_model
from nl2sql.runtime_bundle import BundleChatService, RuntimeFactory, RuntimeManager
from nl2sql.sessions import SessionStore


class ManagedReadiness:
    """Health checking pins one data adapter, just like a chat request."""

    def __init__(self, manager: RuntimeManager) -> None:
        self.manager = manager

    def ready(self) -> None:
        """Check the currently published data adapter."""
        with self.manager.pin() as bundle:
            bundle.database.ready()


@dataclass
class ManagedResources:
    """Sessions/auth/model are shared; old metadata pools drain independently."""

    auth: Authenticator
    sessions: SessionStore
    database: ManagedReadiness
    service: BundleChatService
    manager: RuntimeManager

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
            "ADMIN_CONFIGURATION", "Metadata verification trust anchors are required.", 503
        )
    with ExitStack() as cleanup:
        repository = MetadataRepository(settings.metadata_root)
        cleanup.callback(repository.close)
        sessions = SessionStore(settings.data_dir / "sessions.db", settings.session_retention_days)
        cleanup.callback(sessions.close)
        provider = model or build_model(settings)
        cleanup.callback(provider.close)
        encoder = build_embedding(settings)
        if encoder is not None:
            cleanup.callback(encoder.close)
        version = encoder.identity if encoder else None
        factory = RuntimeFactory(settings, sessions, provider, encoder, version)
        workflow = MetadataWorkflow(
            repository,
            profile.provider(),
            authority,
            builder=BundleBuilder(encoder, version, retrieval_options=settings.retrieval_options),
            runtime_check=factory.check,
        )
        active = repository.control().active
        if active is None:
            raise Failure(
                "NO_ACTIVE_METADATA",
                "Review and publish a bundle before starting the backend.",
                503,
            )
        workflow.verify_record(repository.get(active))
        # Approved snapshots load without discovery; a deployment can require a startup gate.
        if settings.metadata_startup_reconcile:
            workflow.stage()
        auth = Authenticator(settings)

        def close_shared() -> None:
            try:
                provider.close()
            finally:
                if encoder is not None:
                    encoder.close()
                try:
                    sessions.close()
                finally:
                    repository.close()

        manager = RuntimeManager(workflow, factory, auth.replace_principals, close_shared)
        auth.refresh_hook = manager.reload
        cleanup.pop_all()
    return ManagedResources(
        auth, sessions, ManagedReadiness(manager), BundleChatService(manager), manager
    )
