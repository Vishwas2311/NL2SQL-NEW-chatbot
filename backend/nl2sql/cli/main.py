"""Native CLI startup without a frontend or container requirement."""

import argparse
import json
import logging
import os
import sqlite3
from pathlib import Path

import uvicorn

from nl2sql.bootstrap.office_checks import office_preflight
from nl2sql.cli.metadata import MetadataOptions, add_metadata_parser, run_metadata
from nl2sql.cli.office import run_office
from nl2sql.domain.models import Failure
from nl2sql.evaluation.synthetic import initialize
from nl2sql.infrastructure.inference.model import build_model, probe_model
from nl2sql.infrastructure.rate_limit import build_rate_limiter
from nl2sql.infrastructure.retrieval.embeddings import build_embedding
from nl2sql.infrastructure.sessions import SessionStore
from nl2sql.settings import load_settings, selected_environment


def main() -> None:
    """Initialize isolated demo files or run a securely configured API process."""
    parser = argparse.ArgumentParser(description="EWS synthetic NL-to-SQL backend")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in (
        "init-demo",
        "serve",
        "office",
        "validate-config",
        "check-redis",
        "check-model",
        "purge-sessions",
    ):
        command = commands.add_parser(name)
        command.add_argument("--settings", type=Path, default=Path(".local/settings.json"))
        command.add_argument("--port", type=int, default=8000)
        command.add_argument("--metadata-root", type=Path)
        command.add_argument("--env-file", type=Path)
        if name == "serve":
            command.add_argument("--workers", type=int, choices=range(1, 17))
        if name == "office":
            command.add_argument("--approval-file", type=Path)
            command.add_argument("--interval", type=int, default=900)
        if name == "purge-sessions":
            command.add_argument(
                "--limit",
                type=int,
                default=1000,
                help="Maximum expired sessions per batch (1..1000)",
            )
        if name != "office":
            command.add_argument(
                "--catalog", type=Path, default=Path("metadata/synthetic/catalog-v43.json")
            )
    add_metadata_parser(commands.add_parser("metadata", help="Governed schema metadata operations"))
    arguments = parser.parse_args()
    try:
        with selected_environment(arguments.env_file):
            _run(arguments, parser)
    except (ValueError, OSError):
        parser.exit(1, "Configuration or local storage is invalid; values are omitted.\n")


def _run(arguments: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Dispatch commands with one consistent environment for every adapter."""
    if arguments.command in {"metadata", "office"}:
        try:
            if arguments.command == "office":
                run_office(
                    arguments.settings,
                    arguments.env_file,
                    arguments.metadata_root,
                    arguments.approval_file,
                    arguments.port,
                    arguments.interval,
                )
                return
            print(
                json.dumps(
                    run_metadata(MetadataOptions.model_validate(vars(arguments))), default=str
                )
            )
        except Failure as error:
            parser.exit(1, json.dumps({"code": error.code, "message": error.message}) + "\n")
        except ImportError:
            parser.exit(
                1,
                json.dumps(
                    {
                        "code": "OPTIONAL_DEPENDENCY",
                        "message": "Install the selected adapter's approved optional dependency.",
                    }
                )
                + "\n",
            )
        except (ValueError, OSError):
            parser.exit(
                1, "Administrative input or local storage is invalid; no credentials are logged.\n"
            )
        return
    if arguments.command == "init-demo":
        initialize(arguments.settings.parent, arguments.catalog)
        print(
            "Synthetic backend initialized. Credentials: "
            f"{arguments.settings.parent / 'demo-credentials.json'}"
        )
        return
    if arguments.command == "serve" and arguments.workers is not None:
        os.environ["NL2SQL_API_WORKERS"] = str(arguments.workers)
    if arguments.command == "serve" and arguments.metadata_root is not None:
        os.environ["NL2SQL_METADATA_ROOT"] = str(arguments.metadata_root.resolve())
    try:
        configuration = load_settings(arguments.settings, arguments.env_file)
    except (ValueError, OSError):
        parser.exit(1, "Configuration is invalid; values and credentials are omitted.\n")
    if arguments.command == "purge-sessions":
        path = configuration.data_dir / "sessions.db"
        if not path.is_file():
            parser.exit(1, "The configured session store does not exist.\n")
        try:
            sessions = SessionStore(
                path, configuration.session_retention_days, configuration.max_session_bytes
            )
            try:
                removed = sessions.purge_expired(arguments.limit)
            finally:
                sessions.close()
        except (Failure, ValueError, OSError, sqlite3.Error):
            parser.exit(1, "Session maintenance failed; values are omitted.\n")
        print(json.dumps({"deleted_sessions": removed}))
        return
    if arguments.command == "check-redis":
        if configuration.rate_limit_backend != "redis":
            parser.exit(1, "Select Redis explicitly before checking connectivity.\n")
        try:
            limiter = build_rate_limiter(configuration)
            try:
                limiter.ready()
            finally:
                limiter.close()
        except (Failure, ValueError, OSError, ImportError):
            parser.exit(
                1, "Redis connectivity or admission permissions failed; values are omitted.\n"
            )
        print(
            json.dumps(
                {
                    "redis": "available",
                    "admission_commands": "available",
                    "workers": configuration.api_workers,
                }
            )
        )
        return
    if arguments.command in {"check-model", "validate-config"}:
        try:
            if arguments.command == "check-model":
                result = probe_model(configuration)
                output = {
                    "model": "typed_decision_received",
                    "api": configuration.model_api,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                }
            else:
                office_preflight(configuration)
                build_model(configuration).close()
                encoder = build_embedding(configuration)
                if encoder is not None:
                    encoder.close()
                output = {
                    "valid": True,
                    "model": configuration.model_mode,
                    "embedding": configuration.embedding_mode,
                    "sqlite_version": sqlite3.sqlite_version,
                    "api_workers": configuration.api_workers,
                    "active_chat_limit": configuration.max_concurrent_chats,
                    "active_inference_limit": configuration.max_concurrent_inferences,
                    "estimated_retrieval_memory_budget_mb": configuration.retrieval_max_native_mb
                    * configuration.api_workers,
                }
        except Failure as error:
            parser.exit(1, json.dumps({"code": error.code, "message": error.message}) + "\n")
        except (ValueError, OSError):
            parser.exit(1, "Provider configuration is invalid; values are omitted.\n")
        print(json.dumps(output))
        return
    os.environ["EWS_NL2SQL_SETTINGS_FILE"] = str(arguments.settings.resolve())
    if arguments.env_file is not None:
        os.environ["EWS_NL2SQL_ENV_FILE"] = str(arguments.env_file.resolve())
    else:
        os.environ.pop("EWS_NL2SQL_ENV_FILE", None)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    uvicorn.run(
        "nl2sql.bootstrap.factory:create_configured_app",
        factory=True,
        workers=configuration.api_workers,
        limit_concurrency=configuration.http_concurrency_limit,
        host="127.0.0.1",
        port=arguments.port,
    )


if __name__ == "__main__":
    main()
