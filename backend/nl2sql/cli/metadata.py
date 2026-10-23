"""Administrator CLI over the same governed workflows used by the running backend."""

import argparse
import json
import os
import secrets
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path
from threading import Event
from typing import Literal

import jwt
from pydantic import Field, TypeAdapter

from nl2sql.application.metadata.refresh import MetadataRefreshService
from nl2sql.application.metadata.workflow import MetadataWorkflow, StageOutcome
from nl2sql.bootstrap.office_checks import office_preflight
from nl2sql.bootstrap.runtime import RuntimeFactory
from nl2sql.domain.models import Catalog, Failure, FrozenModel, Principal
from nl2sql.domain.physical import PhysicalInventory
from nl2sql.evaluation.synthetic import initialize
from nl2sql.infrastructure.inference.model import DisabledModel
from nl2sql.infrastructure.metadata.builder import BundleBuilder
from nl2sql.infrastructure.metadata.config import (
    SourceProfile,
    authority_from_environment,
    load_profile,
)
from nl2sql.infrastructure.metadata.discovery import FileDiscovery
from nl2sql.infrastructure.metadata.governance import ApprovalAuthority
from nl2sql.infrastructure.metadata.store import MetadataRepository
from nl2sql.infrastructure.rate_limit import MemoryRateLimiter
from nl2sql.infrastructure.retrieval.embeddings import build_embedding
from nl2sql.infrastructure.sessions import SessionStore
from nl2sql.settings import RetrievalOptions, load_settings, selected_environment


class MetadataOptions(FrozenModel):
    """Credentials/tokens are deliberately absent from command-line options."""

    command: Literal["metadata"] = "metadata"
    action: Literal[
        "bootstrap",
        "prepare",
        "sync",
        "status",
        "inspect",
        "approve",
        "publish",
        "rollback",
        "retire",
        "reject",
        "schedule",
        "monitor",
        "demo-trust",
        "sign-demo",
    ]
    root: Path = Path(".local/metadata-v43")
    source: Literal["synthetic", "file", "oracle"] | None = None
    settings: Path | None = None
    file: Path | None = None
    semantic_file: Path | None = None
    grants_file: Path | None = None
    dry_run: bool = False
    candidate_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    approval_file: Path | None = None
    version: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    output: Path | None = None
    enable: bool = False
    disable: bool = False
    interval: int = Field(default=900, ge=5, le=86_400)
    once: bool = False
    env_file: Path | None = None


class ConfiguredDiscovery:
    """Read-only status/review must not require connecting to Oracle."""

    def __init__(self, profile: SourceProfile) -> None:
        self.profile = profile

    def discover(self) -> PhysicalInventory:
        """Construct the authorized provider only when an actual discovery is requested."""
        return self.profile.provider().discover()


class ApprovalFile(FrozenModel):
    """The file carries signed evidence, not trust keys or self-declared permissions."""

    approvals: tuple[str, ...] = Field(max_length=16)


def add_metadata_parser(parser: argparse.ArgumentParser) -> None:
    """Keep legacy init-demo/serve while adding one coherent metadata command group."""
    commands = parser.add_subparsers(dest="action", required=True)
    for action in (
        "bootstrap",
        "prepare",
        "sync",
        "status",
        "inspect",
        "approve",
        "publish",
        "rollback",
        "retire",
        "reject",
        "schedule",
        "monitor",
        "demo-trust",
        "sign-demo",
    ):
        command = commands.add_parser(action)
        command.add_argument("--root", type=Path, default=Path(".local/metadata-v43"))
        command.add_argument("--env-file", type=Path)
        if action in {"bootstrap", "sync", "prepare"}:
            command.add_argument("--source", choices=("synthetic", "file", "oracle"))
            command.add_argument("--settings", type=Path)
            command.add_argument("--file", type=Path)
            command.add_argument("--semantic-file", type=Path)
            command.add_argument("--grants-file", type=Path)
            command.add_argument("--dry-run", action="store_true")
        if action == "prepare":
            command.add_argument("--approval-file", type=Path)
        if action in {"inspect", "approve", "publish", "sign-demo"}:
            command.add_argument("--candidate-id", required=True)
        if action == "approve":
            command.add_argument("--approval-file", type=Path, required=True)
        if action in {"rollback", "retire", "reject"}:
            command.add_argument("--version", required=True)
        if action in {"inspect", "sign-demo"}:
            command.add_argument("--output", type=Path)
        if action == "schedule":
            enabled = command.add_mutually_exclusive_group(required=True)
            enabled.add_argument("--enable", action="store_true")
            enabled.add_argument("--disable", action="store_true")
            command.add_argument("--interval", type=int, default=900)
            command.add_argument("--dry-run", action="store_true")
        if action == "monitor":
            command.add_argument("--once", action="store_true")


def run_metadata(options: MetadataOptions) -> dict[str, object]:
    """Supply one explicit environment to all discovery, query, model and trust adapters."""
    with selected_environment(options.env_file):
        return _run_selected(options)


def _run_selected(options: MetadataOptions) -> dict[str, object]:
    """A first dry run uses temporary storage and leaves the target path untouched."""
    if (
        options.dry_run
        and options.action in {"bootstrap", "sync", "prepare"}
        and not (options.root / "metadata.db").exists()
    ):
        with tempfile.TemporaryDirectory(prefix="nl2sql-bootstrap-preview-") as directory:
            return _run(options, Path(directory), temporary=True)
    return _run(options, options.root.resolve(), temporary=False)


def _prepare_source(options: MetadataOptions, root: Path, temporary: bool) -> SourceProfile:
    original = options.root / "source-profile.json"
    if original.exists():
        profile = load_profile(options.root)
        if options.source is not None and options.source != profile.source:
            raise Failure(
                "SOURCE_MISMATCH",
                "Choose a separate store for a different source profile.",
                "conflict",
            )
        if options.settings is not None:
            settings_path = options.settings.resolve()
            load_settings(settings_path, options.env_file)
            profile = profile.model_copy(update={"settings_path": settings_path})
            if not options.dry_run and not temporary:
                original.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
        return profile
    source = options.source or "synthetic"
    settings_path = options.settings.resolve() if options.settings is not None else None
    if source == "synthetic":
        if settings_path is None:
            settings_path = root / "data/settings.json"
            if not settings_path.exists():
                initialize(root / "data", root / "synthetic-catalog.json")
        settings = load_settings(settings_path, options.env_file)
        profile = SourceProfile(
            source=source,
            source_id="synthetic-banking",
            database_path=settings.data_dir / "banking.db",
            settings_path=settings_path,
        )
    elif source == "file":
        if options.file is None:
            raise ValueError("A file source requires --file")
        inventory = FileDiscovery(options.file).discover()
        profile = SourceProfile(
            source=source,
            source_id=inventory.source_id,
            inventory_path=options.file.resolve(),
            settings_path=settings_path,
        )
    else:
        from nl2sql.infrastructure.metadata.oracle_discovery import (  # pylint: disable=import-outside-toplevel
            OracleDiscovery,
            OracleDiscoverySettings,
        )

        discovery = OracleDiscoverySettings()
        OracleDiscovery(
            discovery
        )  # Authorization guard executes before persisting an office profile.
        profile = SourceProfile(
            source="oracle", source_id=discovery.source_id, settings_path=settings_path
        )
    if not options.dry_run and not temporary:
        root.mkdir(parents=True, exist_ok=True)
        (root / ".metadata-private").touch(exist_ok=True)
        (root / "source-profile.json").write_text(
            profile.model_dump_json(indent=2), encoding="utf-8"
        )
    return profile


def _run(options: MetadataOptions, root: Path, temporary: bool) -> dict[str, object]:
    if options.action == "status" and not (root / "metadata.db").exists():
        return {"active": None, "candidates": [], "schedule_enabled": False}
    profile = (
        _prepare_source(options, root, temporary)
        if options.action in {"bootstrap", "sync", "prepare"}
        else load_profile(root)
    )
    if options.action == "demo-trust":
        return _demo_trust(root, profile)
    if profile.source == "oracle" and options.action != "status":
        if profile.settings_path is None:
            raise Failure(
                "OFFICE_CONFIGURATION",
                "Select protected runtime settings for Oracle metadata operations.",
                "invalid",
            )
        effective = load_settings(profile.settings_path, options.env_file).model_copy(
            update={
                "metadata_root": root,
                "query_backend": "oracle",
                "data_classification": "restricted",
            }
        )
        office_preflight(effective)
    with ExitStack() as cleanup:
        read_only = options.action == "status" or (
            options.dry_run and not temporary and options.action in {"bootstrap", "sync", "prepare"}
        )
        repository = MetadataRepository(root, read_only=read_only)
        cleanup.callback(repository.close)
        if options.action == "status":
            return {
                "control": repository.control().model_dump(),
                "candidates": repository.candidates(),
                "history": repository.history(),
            }
        authority = authority_from_environment()
        factory = None
        settings = None
        encoder = None
        if profile.settings_path is not None and options.action in {
            "bootstrap",
            "prepare",
            "sync",
            "publish",
            "rollback",
            "monitor",
        }:
            settings = load_settings(profile.settings_path, options.env_file)
            if options.dry_run:
                settings = settings.model_copy(update={"index_storage_path": None})
            encoder = build_embedding(settings)
            if encoder is not None:
                cleanup.callback(encoder.close)
            sessions = (
                SessionStore(settings.data_dir / "sessions.db")
                if options.action in {"publish", "rollback"}
                or (options.action == "prepare" and not options.dry_run)
                else None
            )
            if sessions is not None:
                cleanup.callback(sessions.close)
                factory = RuntimeFactory(
                    settings,
                    sessions,
                    DisabledModel(),
                    encoder,
                    encoder.identity if encoder else None,
                    # Publication probes use DisabledModel and never perform inference.
                    inference_admission=MemoryRateLimiter(1),
                )
        workflow = MetadataWorkflow(
            repository,
            ConfiguredDiscovery(profile),
            authority,
            builder=BundleBuilder(
                encoder,
                encoder.identity if encoder else None,
                retrieval_options=settings.retrieval_options if settings else RetrievalOptions(),
                native_dir=settings.graph_native_dir if settings else None,
            ),
            runtime_check=factory.check if factory else None,
        )
        token = os.environ.get("NL2SQL_METADATA_ADMIN_TOKEN")
        if options.action in {"bootstrap", "sync", "prepare"}:
            active = repository.control().active
            catalog = (
                Catalog.model_validate_json(_bounded_read(options.semantic_file, 5_000_000))
                if options.semantic_file
                else (
                    Catalog.model_validate_json(settings.catalog_path.read_text(encoding="utf-8"))
                    if settings is not None and active is None and settings.catalog_path.is_file()
                    else None
                )
            )
            grants = (
                TypeAdapter(tuple[Principal, ...]).validate_json(
                    _bounded_read(options.grants_file, 1_000_000)
                )
                if options.grants_file
                else (settings.principals if settings is not None and active is None else None)
            )
            outcome = workflow.stage(catalog, grants, options.dry_run)
            return (
                _prepare_runtime(options, workflow, factory, outcome, token)
                if options.action == "prepare"
                else outcome.model_dump(mode="json")
            )
        if options.action in {"approve", "publish", "rollback"}:
            return _apply_decision(options, workflow, token)
        return _admin_operation(options, profile, workflow, token)


def _prepare_runtime(
    options: MetadataOptions,
    workflow: MetadataWorkflow,
    factory: RuntimeFactory | None,
    outcome: StageOutcome,
    token: str | None,
) -> dict[str, object]:
    """Preparation derives resources automatically; signed certification remains authoritative."""
    result = outcome.model_dump(mode="json")
    candidate = outcome.candidate_id
    if not options.dry_run and not outcome.issues and candidate is not None:
        if outcome.state == "pending_approval" and options.approval_file is not None:
            manifest = ApprovalFile.model_validate_json(
                _bounded_read(options.approval_file, 150_000)
            )
            workflow.approve(candidate, manifest.approvals, token)
        record = workflow.repository.get(candidate)
        if record.state == "certified":
            workflow.publish(candidate, token)
            result["state"] = "ready"
        elif workflow.repository.control().active == candidate:
            workflow.verify_record(record)
            if factory is None:
                raise Failure(
                    "RUNTIME_CHECK_REQUIRED", "Select runtime settings for preparation.", "conflict"
                )
            factory.check(record.spec)
            result["state"] = "ready"
    result["next_step"] = "serve" if result["state"] == "ready" else "review_metadata"
    return result


def _apply_decision(
    options: MetadataOptions, workflow: MetadataWorkflow, token: str | None
) -> dict[str, object]:
    """Lifecycle decisions all pass through signed governance checks."""
    if options.action == "approve":
        assert options.candidate_id is not None and options.approval_file is not None
        manifest = ApprovalFile.model_validate_json(_bounded_read(options.approval_file, 150_000))
        record = workflow.approve(options.candidate_id, manifest.approvals, token)
        return {"candidate_id": record.spec.id, "state": record.state}
    if options.action == "publish":
        assert options.candidate_id is not None
        return {"active": workflow.publish(options.candidate_id, token)}
    if options.action == "rollback":
        assert options.version is not None
        return {"active": workflow.rollback(options.version, token)}

    raise ValueError("Unsupported lifecycle decision")


def _admin_operation(
    options: MetadataOptions, profile: SourceProfile, workflow: MetadataWorkflow, token: str | None
) -> dict[str, object]:
    """Privileged review and scheduling never alter business certification implicitly."""
    repository = workflow.repository
    root = options.root.resolve()
    authority = workflow.authority
    if authority is None:
        raise Failure("ADMIN_CONFIGURATION", "Administrative trust anchors are required.", "denied")
    action = (
        "approve"
        if options.action == "sign-demo"
        else "review"
        if options.action == "inspect"
        else "schedule"
        if options.action in {"monitor", "schedule"}
        else "retire"
    )
    actor = authority.authenticate(token, action)
    if options.action == "schedule":
        if options.enable:
            profile.provider()  # Office authorization is mandatory before enabling its poller.
        repository.configure_schedule(options.enable, options.interval, options.dry_run, actor.id)
        return {
            "enabled": options.enable,
            "interval_seconds": options.interval,
            "dry_run": options.dry_run,
        }
    if options.action == "monitor":
        refresh = MetadataRefreshService(workflow)
        if options.once:
            return refresh.tick().model_dump(mode="json")
        try:
            refresh.run(Event())
        except KeyboardInterrupt:
            return {"stopped": True}
        return {"stopped": True}
    if options.action in {"retire", "reject"}:
        assert options.version is not None
        repository.retire(options.version, actor.id, rejected=options.action == "reject")
        return {
            "version": options.version,
            "state": "rejected" if options.action == "reject" else "retired",
        }
    assert options.candidate_id is not None
    record = repository.get(options.candidate_id)
    output = options.output or root / (
        "approvals" if options.action == "sign-demo" else "reviews"
    ) / (record.spec.id + ".json")
    if not output.resolve().is_relative_to(root.resolve()):
        raise Failure(
            "PRIVATE_OUTPUT", "Review output must stay in restricted metadata storage.", "denied"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    if options.action == "sign-demo":
        if profile.source != "synthetic" or record.spec.inventory.classification != "synthetic":
            raise Failure("DEMO_ONLY", "Demo signatures cannot certify office metadata.", "denied")
        if not isinstance(authority, ApprovalAuthority):
            raise Failure(
                "DEMO_ONLY", "Demo signing requires the explicit local adapter.", "denied"
            )
        manifest = ApprovalFile(
            approvals=tuple(
                authority.sign_synthetic(key, record.spec.id, profile.source_id)
                for key in authority.reviewers
            )
        )
        output.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    else:
        output.write_text(record.spec.model_dump_json(indent=2), encoding="utf-8")
    return {"private_output": str(output), "synthetic_only": options.action == "sign-demo"}


def _bounded_read(path: Path, limit: int) -> bytes:
    with path.open("rb") as handle:
        value = handle.read(limit + 1)
    if len(value) > limit:
        raise ValueError("Administrative input exceeds its byte budget")
    return value


def _demo_trust(root: Path, profile: SourceProfile) -> dict[str, object]:
    """Explicit fictional bootstrap only; never auto-generates company approval evidence."""
    if profile.source != "synthetic":
        raise Failure(
            "DEMO_ONLY", "Local demo trust is restricted to fictional synthetic sources.", "denied"
        )
    path = root / "demo-credentials.json"
    if path.exists():
        raise FileExistsError("Demo trust already exists")
    values = {"NL2SQL_METADATA_ADMIN_KEY": secrets.token_urlsafe(48)}
    references: list[dict[str, object]] = []
    for role in ("physical", "business", "security"):
        variable = "NL2SQL_METADATA_DEMO_" + role.upper() + "_KEY"
        values[variable] = secrets.token_urlsafe(48)
        references.append({"id": "fictional-demo-" + role, "roles": [role], "key_env": variable})
    values["NL2SQL_METADATA_REVIEWERS"] = json.dumps(references)
    values["NL2SQL_METADATA_ADMIN_TOKEN"] = jwt.encode(
        {
            "sub": "fictional-local-demo-admin",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
            "iss": "nl2sql-metadata-admin",
            "aud": "nl2sql-metadata-admin",
            "actions": ["approve", "publish", "rollback", "schedule", "review", "retire"],
        },
        values["NL2SQL_METADATA_ADMIN_KEY"],
        algorithm="HS256",
    )
    path.write_text(json.dumps(values, indent=2), encoding="utf-8")
    return {"private_credentials": str(path), "synthetic_only": True, "expires_in_seconds": 3600}
