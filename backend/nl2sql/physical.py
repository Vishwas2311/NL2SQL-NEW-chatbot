"""Physical inventory is evidence, never permission to query a discovered object."""

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Literal

from pydantic import Field, model_validator

from nl2sql.domain import FrozenModel, Identifier


def stable_id(prefix: str, *parts: str) -> str:
    """Preserve case/Unicode distinctions through a stable hash, not lossy lowercasing."""
    payload = json.dumps(parts, ensure_ascii=True, separators=(",", ":"))
    stem = re.sub("[^a-z0-9]+", "_", parts[-1].casefold()).strip("_")[:30] or "object"
    return f"{prefix}_{stem}_{hashlib.sha256(payload.encode()).hexdigest()[:20]}"


class PhysicalColumn(FrozenModel):
    """Original names and Oracle NUMBER precision/scale survive discovery unchanged."""

    id: Identifier
    name: str = Field(min_length=1, max_length=128)
    data_type: str = Field(min_length=1, max_length=128)
    position: int = Field(ge=1)
    nullable: bool
    precision: int | None = None
    scale: int | None = None
    length: int | None = None
    comment: str | None = Field(default=None, max_length=4000)


class PhysicalKey(FrozenModel):
    """A declared FK is only a candidate analytical relationship."""

    id: Identifier
    name: str
    kind: Literal["primary", "unique", "foreign"]
    columns: tuple[str, ...]
    target: str | None = None
    target_columns: tuple[str, ...] = ()
    target_owner: str | None = None
    target_constraint: str | None = None
    enabled: bool = True
    validated: bool = True


class PhysicalIndex(FrozenModel):
    """Index observations are not automatically semantic keys."""

    name: str
    columns: tuple[str, ...] = ()
    unique: bool = False


class PhysicalObject(FrozenModel):
    """One owner-qualified physical table/view, including unsupported column types."""

    id: Identifier
    owner: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    kind: Literal["table", "view"]
    columns: tuple[PhysicalColumn, ...]
    keys: tuple[PhysicalKey, ...] = ()
    indexes: tuple[PhysicalIndex, ...] = ()
    dependencies: tuple[str, ...] = ()
    comment: str | None = Field(default=None, max_length=4000)
    definition_digest: str | None = None
    last_ddl_at: str | None = None
    evidence: str
    verification: Literal["verified_physical", "pending_verification"] = "verified_physical"

    @model_validator(mode="after")
    def structural_integrity(self) -> "PhysicalObject":
        """Incomplete or contradictory key records cannot be marked verified."""
        names = {column.name for column in self.columns}
        if len(names) != len(self.columns) or len({column.id for column in self.columns}) != len(
            names
        ):
            raise ValueError("Duplicate physical column")
        for key in self.keys:
            if (
                not key.columns
                or len(set(key.columns)) != len(key.columns)
                or not set(key.columns) <= names
            ):
                raise ValueError("Invalid physical key columns")
            if (
                key.kind == "foreign"
                and key.validated
                and (key.target is None or len(key.columns) != len(key.target_columns))
            ):
                raise ValueError("Incomplete physical foreign key")
        return self


class PhysicalInventory(FrozenModel):
    """Immutable discovery result; discovery timestamps do not create false drift."""

    source_id: str
    source_kind: Literal["synthetic", "file", "oracle"]
    classification: Literal["synthetic", "restricted"] = "restricted"
    owners: tuple[str, ...]
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    objects: tuple[PhysicalObject, ...]
    warnings: tuple[str, ...] = ()
    verification: Literal["verified_physical", "pending_verification"] = "verified_physical"

    @model_validator(mode="after")
    def scope_and_identity(self) -> "PhysicalInventory":
        """Reject owner escapes and collisions; keep inaccessible FK targets as candidates."""
        if not self.owners or len(set(self.owners)) != len(self.owners):
            raise ValueError("Explicit unique schema owners are required")
        if len({item.id for item in self.objects}) != len(self.objects):
            raise ValueError("Duplicate physical object IDs")
        if len({(item.owner, item.name) for item in self.objects}) != len(self.objects):
            raise ValueError("Duplicate owner-qualified object")
        if any(item.owner not in self.owners for item in self.objects):
            raise ValueError("Discovered object outside approved owner scope")
        return self


def inventory_digest(inventory: PhysicalInventory) -> str:
    """Stable normalized schema fingerprint independent of discovery order and row data."""
    records: list[dict[str, object]] = []
    for item in sorted(inventory.objects, key=lambda entry: entry.id):
        record = item.model_dump(mode="json")
        record["columns"] = sorted(record["columns"], key=lambda column: column["name"])
        record["keys"] = sorted(record["keys"], key=lambda key: key["id"])
        record["indexes"] = sorted(record["indexes"], key=lambda index: index["name"])
        record["dependencies"] = sorted(record["dependencies"])
        records.append(record)
    payload = {
        "source_id": inventory.source_id,
        "classification": inventory.classification,
        "owners": sorted(inventory.owners),
        "objects": records,
        "warnings": sorted(inventory.warnings),
        "verification": inventory.verification,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
