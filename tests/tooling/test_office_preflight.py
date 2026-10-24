"""Office checks inspect native versions and paths, without opening services."""

import os

import pytest
from nl2sql.bootstrap.office_checks import office_preflight, wal_patched
from nl2sql.domain.models import Failure


@pytest.mark.parametrize(
    "version,accepted",
    [
        ((3, 50, 4), False),
        ((3, 51, 2), False),
        ((3, 44, 6), True),
        ((3, 50, 7), True),
        ((3, 51, 3), True),
        ((3, 52, 0), True),
    ],
)
def test_wal_patch_versions(version, accepted):
    assert wal_patched(version) == accepted


def test_office_storage_and_runtime_checks_precede_connectivity(settings, tmp_path, monkeypatch):
    configuration = settings.model_copy(
        update={
            "query_backend": "oracle",
            "data_classification": "restricted",
            "data_dir": tmp_path / "runtime",
            "metadata_root": tmp_path / "metadata",
            "catalog_path": tmp_path / "catalog.json",
        }
    )
    monkeypatch.setattr("nl2sql.bootstrap.office_checks.sqlite3.sqlite_version_info", (3, 50, 4))
    with pytest.raises(Failure) as error:
        office_preflight(configuration)
    assert error.value.code == "SQLITE_PATCH_REQUIRED"
    monkeypatch.setattr("nl2sql.bootstrap.office_checks.sqlite3.sqlite_version_info", (3, 51, 3))
    office_preflight(configuration)
    with pytest.raises(Failure, match="absolute"):
        office_preflight(
            configuration.model_copy(update={"data_dir": type(tmp_path)("relative/runtime")})
        )


def test_oracle_metadata_command_checks_runtime_before_opening_store(
    settings, tmp_path, monkeypatch
):
    from nl2sql.cli.metadata import MetadataOptions, run_metadata
    from nl2sql.infrastructure.metadata.config import SourceProfile

    root = tmp_path / "private"
    root.mkdir()
    path = tmp_path / "settings.json"
    path.write_text(settings.model_dump_json(), encoding="utf-8")
    (root / "source-profile.json").write_text(
        SourceProfile(
            source="oracle",
            source_id="synthetic-test-only",
            settings_path=path,
        ).model_dump_json(),
        encoding="utf-8",
    )
    monkeypatch.setattr("nl2sql.bootstrap.office_checks.sqlite3.sqlite_version_info", (3, 50, 4))
    with pytest.raises(Failure) as error:
        run_metadata(MetadataOptions(action="sync", root=root))
    assert error.value.code == "SQLITE_PATCH_REQUIRED" and not (root / "metadata.db").exists()


def test_office_checks_effective_override_root(settings, tmp_path, monkeypatch):
    from nl2sql.cli import office

    configuration = settings.model_copy(
        update={
            "query_backend": "oracle",
            "data_classification": "restricted",
            "metadata_root": tmp_path / "approved",
        }
    )
    monkeypatch.setattr(office, "load_settings", lambda *_: configuration)
    monkeypatch.setattr("nl2sql.bootstrap.office_checks.sqlite3.sqlite_version_info", (3, 51, 3))
    with pytest.raises(Failure) as error:
        office.run_office(
            tmp_path / "settings.json", None, type(tmp_path)("relative"), None, 8000, 900
        )
    assert error.value.code == "OFFICE_STORAGE"


def test_patched_sqlite_without_fts5_is_rejected(monkeypatch):
    import sqlite3

    from nl2sql.bootstrap.office_checks import require_sqlite_runtime

    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 51, 3))

    def unavailable(*_args):
        raise sqlite3.OperationalError("no such module: fts5")

    monkeypatch.setattr(sqlite3, "connect", unavailable)
    with pytest.raises(Failure) as error:
        require_sqlite_runtime()
    assert error.value.code == "SQLITE_FTS5_REQUIRED"


@pytest.mark.skipif(os.name != "nt", reason="Native Windows network path check")
def test_office_storage_rejects_unc_paths(settings, monkeypatch):
    from pathlib import Path

    monkeypatch.setattr("nl2sql.bootstrap.office_checks.require_sqlite_runtime", lambda: None)
    original_resolve = Path.resolve

    def local_only(path, *args, **kwargs):
        assert not path.anchor.startswith("\\\\"), (
            "Reject network paths before Windows resolves them"
        )
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", local_only)
    configuration = settings.model_copy(
        update={
            "query_backend": "oracle",
            "data_classification": "restricted",
            "data_dir": Path(r"\\server\share\restricted-data"),
        }
    )
    with pytest.raises(Failure) as error:
        office_preflight(configuration)
    assert error.value.code == "OFFICE_STORAGE"


def test_dependency_free_report_distinguishes_patch_and_fts5(monkeypatch):
    from nl2sql.bootstrap import sqlite_runtime

    monkeypatch.setattr(sqlite_runtime.sys, "version_info", (3, 13, 17))
    monkeypatch.setattr(sqlite_runtime.sqlite3, "sqlite_version_info", (3, 53, 1))
    assert sqlite_runtime.runtime_report()["compatible"] is True
    monkeypatch.setattr(sqlite_runtime.sqlite3, "sqlite_version_info", (3, 50, 4))
    report = sqlite_runtime.runtime_report()
    assert report["fts5"] is True and report["wal_patched"] is False
    assert report["compatible"] is False


def test_dependency_free_report_rejects_missing_python_tls(monkeypatch):
    import builtins

    from nl2sql.bootstrap import sqlite_runtime

    original = builtins.__import__

    def missing_ssl(name, *args, **kwargs):
        if name == "ssl":
            raise ImportError("synthetic missing TLS library")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_ssl)
    report = sqlite_runtime.runtime_report()
    assert report["tls"] is None and report["compatible"] is False
