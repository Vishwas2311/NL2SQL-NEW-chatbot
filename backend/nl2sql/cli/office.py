"""One office launcher; metadata preparation and monitoring stay outside API workers."""

import json
import os
import subprocess
import sys
import time
from contextlib import ExitStack
from pathlib import Path

from nl2sql.bootstrap.office_checks import office_preflight
from nl2sql.cli.metadata import MetadataOptions, run_metadata
from nl2sql.domain.models import Failure
from nl2sql.settings import load_settings


def run_office(
    settings_path: Path,
    env_file: Path | None,
    root_override: Path | None,
    approval_file: Path | None,
    port: int,
    interval: int,
) -> None:
    """Generate derived resources, require signed certification, then supervise both services."""
    if not 1 <= port <= 65535 or not 5 <= interval <= 86_400:
        raise ValueError("Office port or refresh interval is out of range")
    settings = load_settings(settings_path, env_file)
    root = root_override or settings.metadata_root
    office_preflight(settings.model_copy(update={"metadata_root": root}))
    if settings.query_backend != "oracle" or root is None:
        raise Failure(
            "OFFICE_CONFIGURATION", "Office startup requires Oracle and a metadata root.", "invalid"
        )
    if settings.api_workers != 1:
        raise Failure(
            "OFFICE_CONFIGURATION",
            "The laptop launcher requires one API worker; "
            "use the approved VM supervisor for multiple workers.",
            "invalid",
        )
    if settings.embedding_mode not in {"disabled", "private_http"}:
        raise Failure(
            "OFFICE_CONFIGURATION",
            "Stock office startup supports disabled or private_http embeddings. "
            "Direct local providers require an approved custom process composition.",
            "invalid",
        )
    outcome = run_metadata(
        MetadataOptions(
            action="prepare",
            root=root,
            source="oracle",
            settings=settings_path,
            env_file=env_file,
            approval_file=approval_file,
        )
    )
    print(json.dumps(outcome, default=str), flush=True)
    if outcome["state"] != "ready":
        raise Failure(
            "METADATA_REVIEW_REQUIRED",
            "Discovery is staged. Supply certified business/security mappings and signed review; "
            "rerun office startup.",
            "conflict",
        )
    run_metadata(
        MetadataOptions(
            action="schedule", root=root, enable=True, interval=interval, env_file=env_file
        )
    )
    common = ["--env-file", str(env_file.resolve())] if env_file is not None else []
    api = [
        sys.executable,
        "-m",
        "nl2sql",
        "serve",
        "--settings",
        str(settings_path.resolve()),
        "--metadata-root",
        str(root.resolve()),
        "--port",
        str(port),
        *common,
    ]
    monitor = [
        sys.executable,
        "-m",
        "nl2sql",
        "metadata",
        "monitor",
        "--root",
        str(root.resolve()),
        *common,
    ]
    supervise(api, monitor)


def supervise(api: list[str], monitor: list[str]) -> None:
    """A dead monitor stops the API; Ctrl+C stops both children, including on Windows."""
    children: list[subprocess.Popen[bytes]] = []
    with ExitStack() as cleanup:
        try:
            for command in (monitor, api):
                child = cleanup.enter_context(
                    subprocess.Popen(
                        command,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    )
                )
                children.append(child)
            while all(child.poll() is None for child in children):
                time.sleep(0.25)
            raise Failure(
                "OFFICE_PROCESS_STOPPED",
                "An office process stopped; both services were stopped.",
                "unavailable",
            )
        except KeyboardInterrupt:
            return
        finally:
            for child in reversed(children):
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=5)
