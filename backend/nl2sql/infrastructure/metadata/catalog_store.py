"""Pinned catalog file loading and SQLite schema verification."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock

from nl2sql.application.catalog import validate_catalog
from nl2sql.domain.fingerprints import catalog_hash, digest
from nl2sql.domain.models import Catalog, Failure


class CatalogStore:
    """Atomically publish complete immutable snapshots; failed candidates leave old state."""

    def __init__(self, path: Path, expected_digest: str) -> None:
        self.path = path
        self.expected_digest = expected_digest
        self._lock = Lock()
        self._active: Catalog | None = None

    def load(self, connection: sqlite3.Connection | None = None) -> Catalog:
        """Require an externally pinned digest, never trust a file's own checksum."""
        payload = self.path.read_text(encoding="utf-8")
        if digest(payload) != self.expected_digest:
            raise ValueError("Catalog digest does not match approved pin")
        candidate = Catalog.model_validate_json(payload)
        validate_catalog(candidate)
        if connection is not None:
            validate_sqlite_schema(candidate, connection)
        with self._lock:
            self._active = candidate
        return candidate

    def snapshot(self) -> Catalog:
        """Pin the current snapshot for the entire request."""
        with self._lock:
            if self._active is None:
                raise Failure("CATALOG_UNAVAILABLE", "The catalog is unavailable.", 503)
            return self._active

    @classmethod
    def from_snapshot(cls, catalog: Catalog) -> CatalogStore:
        """Runtime bundles call this only after lifecycle/signature verification."""
        validate_catalog(catalog)
        store = cls(Path("<verified-runtime-bundle>"), catalog_hash(catalog))
        store._active = catalog
        return store


def validate_sqlite_schema(catalog: Catalog, connection: sqlite3.Connection) -> None:
    """Verify SQLite storage types independently of pure semantic validation."""
    validate_catalog(catalog)
    for table in catalog.tables:
        physical = {
            str(row[1]): str(row[2]).upper()
            for row in connection.execute(f'PRAGMA table_info("{table.id}")')
        }
        for column in table.columns:
            expected = "INTEGER" if column.kind == "integer" else "TEXT"
            if physical.get(column.name) != expected:
                raise ValueError("Physical schema type/mapping drift")
