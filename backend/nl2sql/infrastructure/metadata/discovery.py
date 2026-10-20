"""Bounded file/synthetic discovery; no business records are sampled."""

import hashlib
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from nl2sql.domain.physical import (
    PhysicalColumn,
    PhysicalIndex,
    PhysicalInventory,
    PhysicalKey,
    PhysicalObject,
    stable_id,
)


class FileDiscovery:
    """A supplemental inventory must still pass certification and source compatibility."""

    def __init__(self, path: Path, max_bytes: int = 20_000_000) -> None:
        self.path = path
        self.max_bytes = max_bytes

    def discover(self) -> PhysicalInventory:
        """Bound reads before JSON parsing; never import Python or evaluate formulas."""
        with self.path.open("rb") as handle:
            payload = handle.read(self.max_bytes + 1)
        if len(payload) > self.max_bytes:
            raise ValueError("Physical inventory exceeds its byte budget")
        inventory = PhysicalInventory.model_validate_json(payload)
        if inventory.source_kind == "oracle":
            return inventory.model_copy(
                update={
                    "verification": "pending_verification",
                    "warnings": (*inventory.warnings, "offline_copy_requires_live_reconciliation"),
                }
            )
        return inventory


def quoted(name: str) -> str:
    """SQLite PRAGMA does not bind identifiers; quote dictionary-owned names exactly."""
    return '"' + name.replace('"', '""') + '"'


class SyntheticDiscovery:
    """Discover actual fictional SQLite DDL, not a manually prewritten table list."""

    def __init__(
        self, path: Path, source_id: str = "synthetic-banking", max_objects: int = 1000
    ) -> None:
        self.path = path
        self.source_id = source_id
        self.max_objects = max_objects

    def discover(self) -> PhysicalInventory:
        """No SELECT against a business table; row changes cannot affect this inventory."""
        with closing(
            sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)
        ) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            deadline = time.monotonic() + 10
            connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
            rows = connection.execute(
                "SELECT name,type,sql FROM sqlite_master WHERE type IN ('table','view') "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name LIMIT ?",
                (self.max_objects + 1,),
            ).fetchall()
            if len(rows) > self.max_objects:
                raise ValueError("Physical object budget exceeded")
            objects = tuple(self._object(connection, row) for row in rows)
        return PhysicalInventory(
            classification="synthetic",
            source_id=self.source_id,
            source_kind="synthetic",
            owners=("SYNTHETIC",),
            objects=objects,
        )

    def _object(self, connection: sqlite3.Connection, row: sqlite3.Row) -> PhysicalObject:
        name = str(row["name"])
        columns = connection.execute(f"PRAGMA table_info({quoted(name)})").fetchall()
        fields = tuple(
            PhysicalColumn(
                id=stable_id("c", "SYNTHETIC", name, str(column["name"])),
                name=str(column["name"]),
                data_type=str(column["type"]).upper() or "BLOB",
                position=int(column["cid"]) + 1,
                nullable=not bool(column["notnull"]),
            )
            for column in columns
        )
        keys: list[PhysicalKey] = []
        primary = tuple(
            str(column["name"])
            for column in sorted(columns, key=lambda col: int(col["pk"]))
            if column["pk"]
        )
        if primary:
            keys.append(
                PhysicalKey(
                    id=stable_id("k", name, "pk"), name="pk", kind="primary", columns=primary
                )
            )
        indexes: list[PhysicalIndex] = []
        for index in connection.execute(f"PRAGMA index_list({quoted(name)})"):
            values = connection.execute(
                f"PRAGMA index_info({quoted(str(index['name']))})"
            ).fetchall()
            names = tuple(str(value["name"]) for value in values if value["name"] is not None)
            indexes.append(
                PhysicalIndex(name=str(index["name"]), columns=names, unique=bool(index["unique"]))
            )
            if (
                index["unique"]
                and not index["partial"]
                and len(names) == len(values)
                and names != primary
            ):
                keys.append(
                    PhysicalKey(
                        id=stable_id("k", name, str(index["name"])),
                        name=str(index["name"]),
                        kind="unique",
                        columns=names,
                    )
                )
        foreign: dict[int, list[sqlite3.Row]] = {}
        for entry in connection.execute(f"PRAGMA foreign_key_list({quoted(name)})"):
            foreign.setdefault(int(entry["id"]), []).append(entry)
        for entries in foreign.values():
            entries.sort(key=lambda entry: int(entry["seq"]))
            identity = stable_id(
                "k",
                name,
                str(entries[0]["table"]),
                *(str(entry[key]) for entry in entries for key in ("from", "to")),
            )
            keys.append(
                PhysicalKey(
                    id=identity,
                    name=identity,
                    kind="foreign",
                    columns=tuple(str(entry["from"]) for entry in entries),
                    target=stable_id("o", "SYNTHETIC", str(entries[0]["table"])),
                    target_columns=tuple(str(entry["to"]) for entry in entries),
                )
            )
        definition = str(row["sql"]) if row["type"] == "view" else None
        return PhysicalObject(
            id=stable_id("o", "SYNTHETIC", name),
            owner="SYNTHETIC",
            name=name,
            kind="view" if row["type"] == "view" else "table",
            columns=fields,
            keys=tuple(keys),
            indexes=tuple(indexes),
            evidence="SQLite dictionary PRAGMA",
            definition_digest=hashlib.sha256(definition.encode()).hexdigest()
            if definition
            else None,
        )
