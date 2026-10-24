"""Offline office preflight; this does not connect Oracle, inference or identity services."""

import sqlite3
from pathlib import Path

from nl2sql.bootstrap.sqlite_runtime import supports_fts5, wal_patched
from nl2sql.domain.models import Failure
from nl2sql.settings import Settings


def office_preflight(settings: Settings) -> None:
    """Reject known unsafe local runtime/storage before any company connection."""
    if settings.query_backend != "oracle" or settings.data_classification != "restricted":
        return
    require_sqlite_runtime()
    project = Path(__file__).resolve().parents[3]
    for path in (
        settings.data_dir,
        settings.metadata_root,
        settings.index_storage_path,
        settings.catalog_path,
    ):
        if path is None:
            continue
        if not path.is_absolute() or path.resolve().is_relative_to(project):
            raise Failure(
                "OFFICE_STORAGE",
                "Choose absolute protected paths outside the source tree.",
                "invalid",
            )
        if any(
            part.casefold().startswith(("onedrive", "dropbox", "icloud drive", "google drive"))
            for part in path.resolve().parts
        ):
            raise Failure(
                "OFFICE_STORAGE",
                "Restricted storage must be outside synchronized folders.",
                "invalid",
            )


def require_sqlite_runtime() -> None:
    """The linked SQLite library, not the Python version label, determines patch status."""
    if not wal_patched(sqlite3.sqlite_version_info):
        raise Failure(
            "SQLITE_PATCH_REQUIRED",
            "Use an approved Python build linked to SQLite 3.51.3+ "
            "or a documented patched backport.",
            "unavailable",
        )
    if not supports_fts5():
        raise Failure(
            "SQLITE_FTS5_REQUIRED", "Use an approved Python build with SQLite FTS5.", "unavailable"
        )
