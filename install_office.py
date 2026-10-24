"""One Windows entry point: approved runtime, all office packages, private profile and checks."""

import argparse
import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
ARCHIVE = "cpython-3.13.17+20261021-x86_64-pc-windows-msvc-install_only_stripped.tar.gz"
ARCHIVE_HASH = "56cde3b1a1dcc36576753cb408ee0c3568d211baafa0eee40423adc147c480f2"
ARCHIVE_URL = (
    "https://github.com/astral-sh/python-build-standalone/releases/download/20261021/"
    + ARCHIVE.replace("+", "%2B")
)
LOCAL = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local/share")))
PORTABLE = LOCAL / "NL2SQL-Runtimes/20261021"
NATIVE_PROBE = """
import tempfile
from pathlib import Path
import oracledb, redis, sentence_transformers, torch
from nl2sql.evaluation.synthetic import synthetic_catalog
from nl2sql.infrastructure.graph import SurrealGraph
from nl2sql.infrastructure.retrieval.vector_index import SurrealVectorIndex
with tempfile.TemporaryDirectory(prefix='nl2sql-setup-') as directory:
    with SurrealGraph.build(Path(directory)/'probe.surreal.json', synthetic_catalog()) as graph:
        assert 'metric:loan_exposure' in graph.lineage({'table:loans'})
    index = SurrealVectorIndex((('synthetic', (1.0, 0.0)),))
    try:
        assert index.search((1.0, 0.0), {'synthetic'}) == (('synthetic', 1.0),)
    finally:
        index.close()
print('SQLite/FTS5, SurrealDB graph/vector and office Python packages passed local checks.')
"""


class SetupError(ValueError):
    """A setup-only message containing no configuration or secret values."""


def run(command: list[str]) -> None:
    """Use the script's directory, argument arrays and inherited approved pip configuration."""
    subprocess.run(command, cwd=ROOT, check=True)


def compatible(python: Path) -> bool:
    """Reuse the real linked-runtime check before touching any environment."""
    if not python.is_file():
        return False
    try:
        result = subprocess.run(
            [str(python), "-I", str(ROOT / "backend/nl2sql/bootstrap/sqlite_runtime.py")],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.stdout:
        print(result.stdout, flush=True)
    return result.returncode == 0


def extract_runtime(archive: Path, destination: Path) -> Path:
    """Verify bounded bytes before extraction; never replace an existing runtime."""
    with archive.open("rb") as source:
        data = source.read(32_000_001)
    if len(data) > 32_000_000 or hashlib.sha256(data).hexdigest() != ARCHIVE_HASH:
        raise SetupError("Runtime archive hash does not match the qualified candidate")
    if destination.exists():
        raise SetupError("Existing portable runtime is preserved; select another approved Python")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as directory:
        staged = Path(directory) / "runtime"
        staged.mkdir()
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as bundle:
            members = bundle.getmembers()
            if (
                len(members) > 20_000
                or sum(item.size for item in members) > 512_000_000
                or any(not (item.isfile() or item.isdir()) for item in members)
            ):
                raise SetupError("Unexpected runtime archive contents")
            bundle.extractall(staged, filter="data")
        python = staged / "python/python.exe"
        if not compatible(python):
            raise SetupError("Extracted runtime did not pass its diagnostic")
        staged.rename(destination)
    return destination / "python/python.exe"


def select_python(arguments: argparse.Namespace) -> Path:
    """A supplied interpreter/archive or explicitly authorized download supplies the runtime."""
    if arguments.python is not None:
        python = arguments.python.resolve()
        if not compatible(python):
            raise SetupError("Selected Python runtime failed SQLite/FTS5/TLS checks")
        return python
    for python in (
        ROOT / ".venv/Scripts/python.exe",
        Path(sys.executable),
        PORTABLE / "python/python.exe",
    ):
        if compatible(python):
            return python
    if arguments.runtime_archive is not None:
        return extract_runtime(arguments.runtime_archive, PORTABLE)
    if arguments.download_runtime:
        print(
            "Downloading the pinned runtime explicitly selected with --download-runtime.",
            flush=True,
        )
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / ARCHIVE
            with (
                urllib.request.urlopen(ARCHIVE_URL, timeout=60) as response,
                archive.open("wb") as target,
            ):
                received = 0
                while chunk := response.read(1_048_576):
                    received += len(chunk)
                    if received > 32_000_000:
                        raise SetupError("Runtime download exceeded its byte budget")
                    target.write(chunk)
            return extract_runtime(archive, PORTABLE)
    raise SetupError(
        "No compatible runtime found. Rerun with --python <approved-python.exe>, "
        "--runtime-archive <approved-archive>, or --download-runtime after company approval. "
        "See docs/WINDOWS_RUNTIME.md."
    )


def install_packages(python: Path) -> Path:
    """Preserve an incompatible environment before creating a verified replacement."""
    if not compatible(python):
        raise SetupError("Replacement runtime must pass before environment changes")
    environment = ROOT / ".venv"
    executable = environment / "Scripts/python.exe"
    if environment.exists():
        if (
            environment.is_symlink()
            or environment.is_junction()
            or environment.resolve().parent != ROOT.resolve()
        ):
            raise SetupError("Environment must be an ordinary folder inside this project")
    if environment.exists() and not compatible(executable):
        backup = ROOT / (".venv.backup-" + uuid4().hex)
        if backup.resolve().parent != ROOT.resolve():
            raise SetupError("Environment backup must stay inside this project")
        environment.rename(backup)
        print(f"Preserved previous environment: {backup}", flush=True)
    run([str(python), str(ROOT / "setup_env.py"), "--office"])
    run(
        [
            str(executable),
            "-m",
            "pip",
            "install",
            "--only-binary=:all:",
            "-r",
            str(ROOT / "requirements-office-windows.lock"),
        ]
    )
    run([str(executable), "-m", "pip", "check"])
    return executable


def prepare_profile(private_root: Path, embedding_path: Path | None) -> tuple[Path, Path]:
    """Create visible private settings once; preserve a backup before an explicit model change."""
    from dotenv import set_key  # pylint: disable=import-outside-toplevel

    if private_root.anchor.startswith("\\\\"):
        raise SetupError("Choose local private storage outside network folders")
    root = private_root.resolve()
    if (
        root.anchor.startswith("\\\\")
        or root.is_relative_to(ROOT.resolve())
        or any(
            part.casefold().startswith(("onedrive", "dropbox", "icloud drive", "google drive"))
            for part in root.parts
        )
    ):
        raise SetupError("Choose private storage outside source and synchronized folders")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    (root / ".metadata-private").touch(exist_ok=True)
    settings, environment = root / "office.json", root / "office.env"
    if settings.is_symlink() or environment.is_symlink():
        raise SetupError("Private profile files must not be symbolic links")
    if not settings.exists():
        values = json.loads((ROOT / "config/office.example.json").read_text(encoding="utf-8"))
        values.update(
            data_dir=str(root / "runtime"),
            metadata_root=str(root / "metadata"),
            catalog_path=str(root / "metadata/certified-catalog.json"),
        )
        for field in ("embedding_dimension", "embedding_version", "embedding_model"):
            values.pop(field, None)
        with settings.open("x", encoding="utf-8") as target:
            target.write(json.dumps(values, indent=2) + "\n")
    if not environment.exists():
        with environment.open("x", encoding="utf-8") as target:
            target.write((ROOT / "config/office.env.example").read_text(encoding="utf-8"))
    if embedding_path is not None:
        if not embedding_path.is_dir():
            raise SetupError("Select an existing embedding model directory")
        for file in (settings, environment):
            shutil.copy2(file, file.with_name(file.name + ".backup-" + uuid4().hex))
        values = json.loads(settings.read_text(encoding="utf-8"))
        values.update(embedding_mode="local", embedding_local_path=str(embedding_path.resolve()))
        for field in ("embedding_dimension", "embedding_version", "embedding_model"):
            values.pop(field, None)
        temporary = settings.with_name("office.json." + uuid4().hex + ".tmp")
        temporary.write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")
        temporary.replace(settings)
        set_key(environment, "NL2SQL_EMBEDDING_MODE", "local")
        set_key(environment, "NL2SQL_EMBEDDING_LOCAL_PATH", str(embedding_path.resolve()))
        for field in ("DIMENSION", "VERSION", "MODEL"):
            set_key(environment, "NL2SQL_EMBEDDING_" + field, "")
    print(f"Private settings: {settings}\nPrivate connection fields: {environment}", flush=True)
    return settings, environment


def verify_profile(root: Path, live: bool) -> bool:
    """List missing field names, exercise local models, and probe approved HTTP only on --start."""
    from nl2sql.bootstrap.office_checks import office_preflight
    from nl2sql.infrastructure.databases.oracle_factory import OracleExecutionSettings
    from nl2sql.infrastructure.inference.model import build_model
    from nl2sql.infrastructure.metadata.config import authority_from_environment
    from nl2sql.infrastructure.metadata.oracle_discovery import OracleDiscoverySettings
    from nl2sql.infrastructure.metadata.store import MetadataRepository
    from nl2sql.infrastructure.rate_limit import build_rate_limiter
    from nl2sql.infrastructure.retrieval.embeddings import build_embedding
    from nl2sql.settings import load_settings, selected_environment

    with selected_environment(root / "office.env"):
        settings = load_settings(root / "office.json")
        office_preflight(settings)
        missing = []
        for prefix, provider, fields in (
            (
                "QUERY",
                OracleExecutionSettings(),
                (
                    "dsn",
                    "user",
                    "password",
                    "apply_procedure",
                    "reset_procedure",
                    "approved_environment",
                    "owner_authorized",
                    "network_authorized",
                    "readonly_grants_verified",
                    "context_procedures_verified",
                ),
            ),
            (
                "DISCOVERY",
                OracleDiscoverySettings(),
                (
                    "dsn",
                    "user",
                    "password",
                    "owners",
                    "approved_environment",
                    "owner_authorized",
                    "network_authorized",
                ),
            ),
        ):
            missing.extend(
                "NL2SQL_" + prefix + "_" + field.upper()
                for field in fields
                if not getattr(provider, field)
            )
        if not settings.tokens and settings.jwt_secret is None:
            missing.append("NL2SQL_TOKENS or NL2SQL_JWT_SECRET (approved identity configuration)")
        has_publication = False
        if settings.metadata_root and (settings.metadata_root / "metadata.db").is_file():
            repository = MetadataRepository(settings.metadata_root, read_only=True)
            try:
                has_publication = repository.control().active is not None
            finally:
                repository.close()
        if not settings.principals and not has_publication:
            missing.append("NL2SQL_PRINCIPALS (server-owned user grants)")
        for field in ("ADMIN_KEY", "ADMIN_TOKEN", "REVIEWERS"):
            if not os.environ.get("NL2SQL_METADATA_" + field):
                missing.append("NL2SQL_METADATA_" + field)
        if settings.model_mode != "disabled" and (
            not settings.model_endpoint or settings.model_name.startswith("SET_")
        ):
            missing.append("NL2SQL_MODEL_ENDPOINT and NL2SQL_MODEL_NAME")
        if settings.model_mode != "disabled" and not settings.model_token_count_endpoint:
            missing.append("NL2SQL_MODEL_TOKEN_COUNT_ENDPOINT")
        encoder = build_embedding(settings)
        if encoder is not None:
            try:
                if settings.embedding_mode == "local" or live:
                    encoder.encode(("synthetic metadata installation probe",))
                    print(
                        "Embedding loader and encoding passed; dimension:",
                        encoder.settings.embedding_dimension,
                    )
            finally:
                encoder.close()
        if missing:
            print(
                "Packages installed; office startup is blocked by these missing fields/approvals:"
            )
            print("\n".join(missing))
            print(
                "Fill the private profile locally. Approval flags attest real approvals; do not guess them."
            )
            return False
        authority = authority_from_environment()
        if authority is None or not {"physical", "business", "security"}.issubset(
            role for reviewer in authority.reviewers.values() for role in reviewer.roles
        ):
            raise SetupError(
                "Configure trusted physical, business and security reviewers before startup"
            )
        if live:
            authority.authenticate(os.environ.get("NL2SQL_METADATA_ADMIN_TOKEN"), "schedule")
        provider = build_model(settings)
        try:
            if live and settings.model_mode != "disabled":
                provider.plan(
                    "Synthetic installation probe: ask for clarification.",
                    '{"metrics":[],"schema_records":[]}',
                    time.time() + settings.model_timeout_seconds,
                )
        finally:
            provider.close()
        if live:
            limiter = build_rate_limiter(settings)
            try:
                limiter.ready()
            finally:
                limiter.close()
        print(
            "Local configuration passed. Oracle and signed metadata are checked by office preparation before API startup."
        )
        return True


def install(arguments: argparse.Namespace) -> None:
    """Fail fast through one reproducible sequence; no activation or policy changes."""
    if arguments.embedding_path is not None and not arguments.embedding_path.is_dir():
        raise SetupError("Select the existing local embedding model folder")
    python = install_packages(select_python(arguments))
    command = [
        str(python),
        str(ROOT / "install_office.py"),
        "--private-root",
        str(arguments.private_root),
    ]
    run(
        [
            *command,
            "--configure",
            *(
                ["--embedding-path", str(arguments.embedding_path)]
                if arguments.embedding_path
                else []
            ),
        ]
    )
    run([str(python), "-c", NATIVE_PROBE])
    if arguments.check:
        run([str(python), str(ROOT / "scripts/check.py")])
    run([*command, "--verify", *(["--start"] if arguments.start else [])])
    if arguments.start:
        run(
            [
                str(python),
                "-m",
                "nl2sql",
                "office",
                "--settings",
                str(arguments.private_root / "office.json"),
                "--env-file",
                str(arguments.private_root / "office.env"),
            ]
        )


def main() -> None:
    """Installation is local; --start explicitly requests approved provider probes and startup."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, help="Company-approved Python executable")
    parser.add_argument(
        "--runtime-archive", type=Path, help="Approved pinned portable runtime archive"
    )
    parser.add_argument(
        "--download-runtime",
        action="store_true",
        help="Download pinned runtime; use only after company approval",
    )
    parser.add_argument("--private-root", type=Path, default=LOCAL / "NL2SQL/office")
    parser.add_argument(
        "--embedding-path", type=Path, help="Existing MiniLM/Sentence Transformers model folder"
    )
    parser.add_argument(
        "--check", action="store_true", help="Also run the full mandatory quality checker"
    )
    parser.add_argument(
        "--start",
        action="store_true",
        help="Probe approved providers, then run office preparation/supervision",
    )
    parser.add_argument("--configure", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--verify", action="store_true", help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    if arguments.private_root.anchor.startswith("\\\\"):
        parser.error("Choose local private storage outside network folders")
    arguments.private_root = arguments.private_root.resolve()
    if arguments.embedding_path is not None:
        arguments.embedding_path = arguments.embedding_path.resolve()
    if sys.platform != "win32" or platform.machine().casefold() not in {"amd64", "x86_64"}:
        parser.error(
            "This complete CPU package installer targets Windows x64; use setup_env.py on other systems"
        )
    try:
        if arguments.configure:
            prepare_profile(arguments.private_root, arguments.embedding_path)
        elif arguments.verify:
            from nl2sql.domain.models import Failure

            try:
                if not verify_profile(arguments.private_root, arguments.start):
                    raise SystemExit(2)
            except Failure as error:
                parser.exit(2, f"Office check blocked: {error.code}: {error.message}\n")
        else:
            install(arguments)
    except subprocess.CalledProcessError as error:
        parser.exit(
            error.returncode or 1, "Setup stopped at the failed step; the app was not started.\n"
        )
    except SetupError as error:
        parser.exit(1, str(error) + "\n")
    except (
        OSError,
        ValueError,
        ImportError,
        RuntimeError,
        subprocess.TimeoutExpired,
        tarfile.TarError,
    ):
        parser.exit(
            1,
            "Setup failed. Check the selected runtime, model folder and private configuration; no secret values are printed.\n",
        )


if __name__ == "__main__":
    main()
