"""Atomic local activation, request leases, current-grant checks and safe resource retirement."""

import json
import secrets
from collections.abc import Callable, Generator
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeout
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from threading import Lock, RLock

from nl2sql.bundle_build import grant_digest
from nl2sql.catalog import CatalogStore, catalog_hash, digest
from nl2sql.config import Settings
from nl2sql.database import SQLiteDatabase
from nl2sql.domain import Answer, Catalog, CompiledQuery, Failure, Principal
from nl2sql.drift import analyze_impact, policy_digest, schema_changes
from nl2sql.metadata_store import BundleSpec
from nl2sql.metadata_workflow import MetadataWorkflow
from nl2sql.model import ModelProvider
from nl2sql.planning import principal_hash
from nl2sql.ports import QueryExecutor
from nl2sql.retrieval import EmbeddingProvider, Retriever
from nl2sql.security import SQLValidator
from nl2sql.service import ChatService
from nl2sql.sessions import SessionStore
from nl2sql.vector_index import VectorIndexFactory


@dataclass(frozen=True)
class RuntimeMetadataBundle:
    """All semantic components of a request are selected by one immutable reference."""

    version: str
    spec: BundleSpec
    catalog: Catalog
    service: ChatService
    database: QueryExecutor
    retriever: Retriever
    release_search: Callable[[], None]

    def close(self) -> None:
        """Called only after the last request lease releases this bundle."""
        try:
            self.database.close()
        finally:
            self.release_search()


@dataclass
class SearchReference:
    """Unchanged approved corpora share one index and encoder build."""

    future: Future[Retriever]
    references: int = 0


class RuntimeFactory:
    """Build expensive candidates without holding the manager's short swap lock."""

    def __init__(
        self,
        settings: Settings,
        sessions: SessionStore,
        model: ModelProvider,
        encoder: EmbeddingProvider | None = None,
        encoder_version: str | None = None,
        executor_factory: Callable[[SQLValidator], QueryExecutor] | None = None,
        vector_factory: VectorIndexFactory | None = None,
    ) -> None:
        self.settings = settings
        self.sessions = sessions
        self.model = model
        self.embedding = (encoder, encoder_version, vector_factory)
        self.executor_factory = executor_factory
        self._searches: dict[str, SearchReference] = {}
        self._lock = RLock()

    def build(
        self, spec: BundleSpec, guard: Callable[[CompiledQuery, Principal], None] | None = None
    ) -> RuntimeMetadataBundle:
        """A failed build closes all new handles and leaves the old bundle untouched."""
        if spec.catalog is None or spec.artifacts is None or spec.issues:
            raise Failure("METADATA_INCOMPLETE", "A complete metadata bundle is required.", 503)
        catalog = spec.catalog.model_copy(update={"approved": True})
        if (
            catalog_hash(catalog) != spec.artifacts.catalog_digest
            or spec.artifacts.encoder_version != self.embedding[1]
        ):
            raise Failure("METADATA_INTEGRITY", "Runtime metadata versions disagree.", 503)
        validator = SQLValidator(catalog, secrets.token_bytes(32), spec.id, guard)
        with ExitStack() as cleanup:
            if self.executor_factory is not None:
                database = self.executor_factory(validator)
            elif self.settings.query_backend == "oracle":
                from nl2sql.oracle_factory import oracle_executor  # pylint: disable=import-outside-toplevel

                database = oracle_executor(validator)
            else:
                if spec.inventory.source_kind == "oracle":
                    raise Failure(
                        "BACKEND_MISMATCH",
                        "Oracle metadata requires its approved query executor.",
                        503,
                    )
                database = SQLiteDatabase(
                    self.settings.data_dir / "banking.db", validator, self.settings
                )
            cleanup.callback(database.close)
            search, release = self._search(catalog, spec.principals)
            cleanup.callback(release)
            if spec.artifacts.vector_digest is not None:
                if (
                    digest(json.dumps(search.vector_manifest(), sort_keys=True))
                    != spec.artifacts.vector_digest
                ):
                    raise Failure("VECTOR_VERSION", "Vector/index/model compatibility failed.", 503)
            service = ChatService(
                self.settings,
                CatalogStore.from_snapshot(catalog),
                search,
                self.model,
                database,
                self.sessions,
                spec.id,
            )
            result = RuntimeMetadataBundle(
                spec.id, spec, catalog, service, database, search, release
            )
            cleanup.pop_all()
        return result

    def check(self, spec: BundleSpec) -> None:
        """Publication checks the same resource builder used by request-time activation."""
        bundle = self.build(spec)
        try:
            bundle.database.ready()
        finally:
            bundle.close()

    def _search(
        self, catalog: Catalog, principals: tuple[Principal, ...]
    ) -> tuple[Retriever, Callable[[], None]]:
        key = catalog_hash(catalog) + grant_digest(principals) + str(self.embedding[1])
        with self._lock:
            reference = self._searches.get(key)
            owner = reference is None
            if reference is None:
                reference = SearchReference(Future())
                self._searches[key] = reference
            reference.references += 1

        def release() -> None:
            with self._lock:
                reference.references -= 1
                if reference.references == 0:
                    if reference.future.done() and reference.future.exception() is None:
                        reference.future.result().close()
                    del self._searches[key]

        try:
            if owner:
                try:
                    search = Retriever(
                        catalog,
                        principals,
                        self.embedding[0],
                        self.embedding[2],
                        self.settings.retrieval_options,
                    )
                except BaseException as error:
                    reference.future.set_exception(error)
                    raise
                reference.future.set_result(search)
            return reference.future.result(timeout=self.settings.request_timeout_seconds), release
        except FutureTimeout as error:
            release()
            raise Failure("INDEX_BUSY", "Search resources are still preparing.", 503) from error
        except BaseException:
            release()
            raise


@dataclass
class BundleLease:
    """Lease counts are mutable lifecycle state, separate from semantic snapshots."""

    bundle: RuntimeMetadataBundle
    users: int = 0
    retired: bool = False


@dataclass
class RuntimeState:
    """Mutable lease bookkeeping protected by the manager lock."""

    active: BundleLease | None = None
    entries: dict[int, BundleLease] = field(default_factory=dict[int, BundleLease])
    closed: bool = False


class RuntimeManager:
    """Durable pointer CAS coordinates processes; the in-memory swap is process-local."""

    def __init__(
        self,
        workflow: MetadataWorkflow,
        factory: RuntimeFactory,
        on_activate: Callable[[tuple[Principal, ...]], None] | None = None,
        on_drained: Callable[[], None] | None = None,
    ) -> None:
        self.workflow = workflow
        self.factory = factory
        self.on_activate = on_activate
        self.on_drained = on_drained
        self._lock = RLock()
        self._reload_lock = Lock()
        self._state = RuntimeState()
        self.reload()

    def reload(self) -> None:
        """No discovery on chat: only read the protected local publication pointer."""
        with self._reload_lock:
            with self._lock:
                if self._state.closed:
                    raise Failure("RUNTIME_CLOSED", "The metadata runtime is shutting down.", 503)
                control = self.workflow.repository.control()
                if (
                    self._state.active is not None
                    and self._state.active.bundle.version == control.active
                ):
                    return
                if control.active is None:
                    raise Failure(
                        "NO_ACTIVE_METADATA",
                        "Publish an approved metadata bundle before serving.",
                        503,
                    )
            record = self.workflow.repository.get(control.active)
            if record.state != "published":
                raise Failure(
                    "METADATA_INTEGRITY", "The active metadata publication state is invalid.", 503
                )
            self.workflow.verify_record(record, published=True)
            candidate = self.factory.build(record.spec, self._guard)
            old: BundleLease | None = None
            close_old = False
            with self._lock:
                if (
                    self._state.closed
                    or self.workflow.repository.control().active != candidate.version
                ):
                    candidate.close()
                    raise Failure(
                        "PUBLICATION_CONFLICT",
                        "The publication changed while preparing runtime resources.",
                        409,
                    )
                old = self._state.active
                self._state.active = BundleLease(candidate)
                self._state.entries[id(self._state.active)] = self._state.active
                if self.on_activate is not None:
                    self.on_activate(record.spec.principals)
                if old is not None:
                    old.retired = True
                    if old.users == 0:
                        del self._state.entries[id(old)]
                        close_old = True
            if old is not None and close_old:
                old.bundle.close()

    @contextmanager
    def pin(self) -> Generator[RuntimeMetadataBundle]:
        """One bundle is retained from planning through response authorization."""
        self.reload()
        with self._lock:
            if self._state.closed or self._state.active is None:
                raise Failure("RUNTIME_CLOSED", "No request runtime is available.", 503)
            entry = self._state.active
            entry.users += 1
        try:
            yield entry.bundle
        finally:
            close = False
            with self._lock:
                entry.users -= 1
                if entry.retired and entry.users == 0:
                    self._state.entries.pop(id(entry), None)
                    close = True
            if close:
                entry.bundle.close()
            self._finish_shutdown()

    def assert_identity(self, principal: Principal) -> None:
        """Revocations in another process fail closed until this worker loads the new bundle."""
        with self._lock:
            active = self._state.active
            if active is None or self.workflow.repository.control().active != active.bundle.version:
                raise Failure(
                    "CATALOG_CHANGED", "Metadata changed; retry with current authorization.", 409
                )
            current = next(
                (user for user in active.bundle.spec.principals if user.id == principal.id), None
            )
            if current is None or principal_hash(current) != principal_hash(principal):
                raise Failure(
                    "DENIED", "Current permissions no longer authorize this request.", 403
                )

    def _guard(self, query: CompiledQuery, principal: Principal) -> None:
        self.assert_identity(principal)
        with self._lock:
            active = self._state.active
            entry = next(
                (
                    item
                    for item in self._state.entries.values()
                    if item.bundle.version == query.bundle_version
                ),
                None,
            )
            assert active is not None
            if (
                entry is None
                or query.validated_plan.plan.view_id
                in self.workflow.repository.control().blocked_views
            ):
                raise Failure(
                    "SCHEMA_DRIFT", "This report is blocked pending metadata reconciliation.", 409
                )
            if entry is not active:
                if policy_digest(entry.bundle.catalog) != policy_digest(active.bundle.catalog):
                    raise Failure("CAPABILITY_DENIED", "The policy version changed.", 403)
                impact = analyze_impact(
                    schema_changes(entry.bundle.spec.inventory, active.bundle.spec.inventory),
                    entry.bundle.catalog,
                    entry.bundle.spec.inventory,
                )
                if query.validated_plan.plan.view_id in impact.blocked_views:
                    raise Failure(
                        "SCHEMA_DRIFT", "The pinned source mapping is no longer compatible.", 409
                    )

    def close(self) -> None:
        """Outstanding leases drain before pools, indexes or shared services are closed."""
        ready: list[BundleLease] = []
        with self._lock:
            self._state.closed = True
            for entry in tuple(self._state.entries.values()):
                entry.retired = True
                if entry.users == 0:
                    ready.append(entry)
                    del self._state.entries[id(entry)]
        for entry in ready:
            entry.bundle.close()
        self._finish_shutdown()

    def _finish_shutdown(self) -> None:
        callback = None
        with self._lock:
            if self._state.closed and not self._state.entries and self.on_drained is not None:
                callback = self.on_drained
                self.on_drained = None
        if callback is not None:
            callback()


class BundleChatService:
    """FastAPI keeps the same chat contract while metadata versions change underneath it."""

    def __init__(self, manager: RuntimeManager) -> None:
        self.manager = manager

    def chat(
        self,
        question: str,
        session_id: str | None,
        principal: Principal,
        claimed_user_id: str | None,
        spans: dict[str, float],
    ) -> Answer:
        """Retain one snapshot and reauthorize before returning any result."""
        with self.manager.pin() as bundle:
            self.manager.assert_identity(principal)
            answer = bundle.service.chat(question, session_id, principal, claimed_user_id, spans)
            self.manager.assert_identity(principal)
            return answer
