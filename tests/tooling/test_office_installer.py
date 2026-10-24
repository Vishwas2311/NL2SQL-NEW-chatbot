"""One entry point preserves private files and refuses unsafe runtime changes."""

import hashlib
import io
import json
import tarfile
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest
from nl2sql.settings import load_settings

import install_office as installer


def test_generated_profile_accepts_model_path_entered_later_in_env(tmp_path):
    settings, environment = installer.prepare_profile(tmp_path / "private", None)
    model = tmp_path / "MiniLM"
    model.mkdir()
    with environment.open("a", encoding="utf-8") as target:
        target.write(f"\nNL2SQL_EMBEDDING_MODE=local\nNL2SQL_EMBEDDING_LOCAL_PATH='{model}'\n")
    loaded = load_settings(settings, env_file=environment)
    assert loaded.embedding_mode == "local"
    assert loaded.embedding_local_path == model
    assert "embedding_dimension" not in loaded.model_fields_set


def test_profile_is_windows_local_and_repeatable(tmp_path, monkeypatch):
    project = Path(__file__).resolve().parents[2]
    monkeypatch.setattr(installer, "ROOT", project)
    root = tmp_path / "private"
    settings, environment = installer.prepare_profile(root, None)
    values = json.loads(settings.read_text())
    assert Path(values["data_dir"]) == root / "runtime"
    assert Path(values["metadata_root"]) == root / "metadata"
    assert "embedding_dimension" not in values
    assert "embedding_model" not in values
    assert "embedding_version" not in values
    assert "NL2SQL_QUERY_DSN=" in environment.read_text()
    environment.write_text("# keep private settings\n")
    installer.prepare_profile(root, None)
    assert environment.read_text() == "# keep private settings\n"
    model = tmp_path / "MiniLM with spaces"
    model.mkdir()
    installer.prepare_profile(root, model)
    values = json.loads(settings.read_text())
    assert values["embedding_mode"] == "local"
    assert values["embedding_local_path"] == str(model)
    assert "embedding_dimension" not in values
    assert list(root.glob("office.env.backup-*"))
    assert "keep private settings" in environment.read_text()


def test_bad_archive_and_source_tree_profile_are_rejected_before_writing(tmp_path):
    archive = tmp_path / "untrusted.tar.gz"
    archive.write_bytes(b"wrong bytes")
    target = tmp_path / "python"
    with pytest.raises(ValueError, match="hash"):
        installer.extract_runtime(archive, target)
    assert not target.exists()
    with pytest.raises(ValueError, match="outside"):
        installer.prepare_profile(installer.ROOT / ".local/private-test", None)


def test_environment_is_preserved_until_replacement_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(installer, "ROOT", tmp_path)
    old = tmp_path / ".venv"
    old.mkdir()
    (old / "sentinel").write_bytes(b"keep old environment")
    monkeypatch.setattr(installer, "compatible", lambda *_: False)
    monkeypatch.setattr(
        installer, "run", lambda *_: pytest.fail("No installation before validation")
    )
    with pytest.raises(ValueError, match="runtime"):
        installer.install_packages(tmp_path / "bad-python.exe")
    assert (old / "sentinel").read_bytes() == b"keep old environment"
    assert not list(tmp_path.glob(".venv.backup-*"))


def test_cli_uses_file_location_and_stops_before_start_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(installer, "ROOT", tmp_path)
    monkeypatch.chdir(tmp_path.parent)
    monkeypatch.setattr(installer, "select_python", lambda *_: tmp_path / "approved-python")
    monkeypatch.setattr(installer, "install_packages", lambda *_: tmp_path / ".venv/python")
    calls = []

    def run(command):
        calls.append(command)
        if "--verify" in command:
            raise installer.subprocess.CalledProcessError(2, command)

    monkeypatch.setattr(installer, "run", run)
    arguments = Namespace(
        python=None,
        runtime_archive=None,
        download_runtime=False,
        private_root=tmp_path.parent / "private",
        embedding_path=None,
        check=False,
        start=True,
        configure=False,
        verify=False,
    )
    with pytest.raises(installer.subprocess.CalledProcessError):
        installer.install(arguments)
    assert any("--configure" in call for call in calls)
    assert not any("office" in call for call in calls)


@pytest.mark.parametrize(
    "error", [OSError("blocked"), installer.subprocess.TimeoutExpired("probe", 30)]
)
def test_bad_candidate_probe_does_not_abort_discovery(tmp_path, monkeypatch, error):
    candidate = tmp_path / "python.exe"
    candidate.touch()

    def fail(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(installer.subprocess, "run", fail)
    assert installer.compatible(candidate) is False


@pytest.mark.parametrize("member_name", ["python/python.exe", "../escaped.exe"])
def test_qualified_archive_extraction_and_path_escape(tmp_path, monkeypatch, member_name):
    archive = tmp_path / "runtime.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        item = tarfile.TarInfo(member_name)
        item.size = 5
        bundle.addfile(item, io.BytesIO(b"probe"))
    monkeypatch.setattr(installer, "ARCHIVE_HASH", hashlib.sha256(archive.read_bytes()).hexdigest())
    monkeypatch.setattr(installer, "compatible", lambda path: path.is_file())
    destination = tmp_path / "runtime"
    if member_name.startswith(".."):
        with pytest.raises(tarfile.FilterError):
            installer.extract_runtime(archive, destination)
        assert not destination.exists()
        assert not (tmp_path / "escaped.exe").exists()
    else:
        executable = installer.extract_runtime(archive, destination)
        assert executable.read_bytes() == b"probe"
        with pytest.raises(ValueError, match="preserved"):
            installer.extract_runtime(archive, destination)


def test_installer_resolves_model_relative_to_callers_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    model = tmp_path / "my model"
    model.mkdir()
    monkeypatch.setattr(
        installer.sys, "argv", ["install_office.py", "--embedding-path", "my model"]
    )
    monkeypatch.setattr(installer.sys, "platform", "win32")
    monkeypatch.setattr(installer.platform, "machine", lambda: "AMD64")
    captured = []
    monkeypatch.setattr(installer, "install", captured.append)
    installer.main()
    assert captured[0].embedding_path == model.resolve()


def test_linked_environment_is_never_modified(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    link = project / ".venv"
    if installer.os.name == "nt":
        installer.subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(external)], check=True, capture_output=True
        )
    else:
        link.symlink_to(external, target_is_directory=True)
    monkeypatch.setattr(installer, "ROOT", project)
    monkeypatch.setattr(installer, "compatible", lambda *_: True)
    monkeypatch.setattr(
        installer, "run", lambda *_: pytest.fail("Never modify linked environments")
    )
    try:
        with pytest.raises(ValueError, match="ordinary"):
            installer.install_packages(tmp_path / "approved-python")
    finally:
        link.rmdir() if installer.os.name == "nt" else link.unlink()


@pytest.mark.parametrize(
    "failure", [RuntimeError("private backend details"), installer.SetupError("safe setup message")]
)
def test_installer_expected_errors_do_not_print_private_details(monkeypatch, capsys, failure):
    monkeypatch.setattr(installer.sys, "argv", ["install_office.py"])
    monkeypatch.setattr(installer.sys, "platform", "win32")
    monkeypatch.setattr(installer.platform, "machine", lambda: "AMD64")

    def fail(_arguments):
        raise failure

    monkeypatch.setattr(installer, "install", fail)
    with pytest.raises(SystemExit) as exit_code:
        installer.main()
    assert exit_code.value.code == 1
    output = capsys.readouterr().err
    assert "private backend details" not in output
    assert "Traceback" not in output


@pytest.mark.parametrize("live", [False, True])
@pytest.mark.parametrize("published", [False, True])
def test_http_embedding_probe_requires_explicit_start(
    tmp_path, monkeypatch, capsys, live, published
):
    root = tmp_path / "private"
    _, environment = installer.prepare_profile(root, None)
    environment.write_text("NL2SQL_EMBEDDING_MODE=private_http\n", encoding="utf-8")
    calls = []
    encoder = SimpleNamespace(
        encode=lambda texts: calls.append(texts),
        close=lambda: calls.append("close"),
        settings=SimpleNamespace(embedding_dimension=2),
    )
    monkeypatch.setattr("nl2sql.bootstrap.office_checks.office_preflight", lambda _: None)
    monkeypatch.setattr(
        "nl2sql.infrastructure.retrieval.embeddings.build_embedding", lambda _: encoder
    )
    if published:
        metadata = root / "metadata"
        metadata.mkdir()
        (metadata / "metadata.db").touch()
        monkeypatch.setattr(
            "nl2sql.infrastructure.metadata.store.MetadataRepository",
            lambda *_args, **_kwargs: SimpleNamespace(
                control=lambda: SimpleNamespace(active="signed-existing-publication"),
                close=lambda: None,
            ),
        )
    assert (
        installer.verify_profile(root, live) is False
    )  # Missing office fields; no other providers run.
    assert len(calls) == (2 if live else 1)
    assert calls[-1] == "close"
    assert ("NL2SQL_PRINCIPALS" in capsys.readouterr().out) is (not published)
