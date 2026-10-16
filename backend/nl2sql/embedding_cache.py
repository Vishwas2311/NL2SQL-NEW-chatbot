"""Restricted vector snapshots; signed manifests remain the compatibility authority."""

import hashlib
import json
import logging
import re
import tempfile
from pathlib import Path

from pydantic import Field

from nl2sql.domain import FrozenModel
from nl2sql.vector_index import normalized


class VectorSnapshot(FrozenModel):
    """Contains only content hashes and vectors, never original metadata text or rows."""

    classification: str = "restricted"
    identity: str
    dimension: int
    normalization: str
    entries: dict[str, tuple[float, ...]] = Field(max_length=100_000)
    checksum: str


def restricted_path(root: Path, identity: str) -> Path:
    """Refuse unmarked storage, including resolved symlink escapes from restricted roots."""
    resolved = root.resolve()
    if re.fullmatch(r"[a-f0-9]{64}", identity) is None:
        raise ValueError("Invalid embedding identity")
    if not any(
        (parent / ".metadata-private").is_file() for parent in (resolved, *resolved.parents)
    ):
        raise ValueError("Index snapshots require marked restricted storage")
    resolved.mkdir(parents=True, exist_ok=True)
    target = resolved / ("vectors-" + identity + ".json")
    if target.is_symlink():
        raise ValueError("Index snapshot cannot be a symbolic link")
    return target


def checksum(entries: dict[str, tuple[float, ...]]) -> str:
    """Detect incomplete or corrupted cache payloads; this checksum is not certification."""
    return hashlib.sha256(
        json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def load_vectors(
    path: Path, identity: str, dimension: int, normalization: str
) -> dict[str, tuple[float, ...]]:
    """Corrupt caches are disposable; rebuilding still has to match the signed bundle digest."""
    if not path.exists():
        return {}
    try:
        with path.open("rb") as stream:
            data = stream.read(20_000_001)
        if len(data) > 20_000_000:
            raise ValueError("Cache exceeds its byte budget")
        snapshot = VectorSnapshot.model_validate_json(data)
        if (snapshot.identity, snapshot.dimension, snapshot.normalization) != (
            identity,
            dimension,
            normalization,
        ) or snapshot.checksum != checksum(snapshot.entries):
            raise ValueError("Cache compatibility mismatch")
        for key, vector in snapshot.entries.items():
            if len(key) != 64 or len(vector) != dimension:
                raise ValueError("Invalid cache entry")
            unit = normalized(vector)
            if normalization == "l2" and any(
                abs(a - b) > 1e-10 for a, b in zip(vector, unit, strict=True)
            ):
                raise ValueError("Invalid cached normalization")
        return snapshot.entries
    except (ValueError, OSError):
        logging.getLogger("nl2sql").warning("embedding_cache_rebuild reason=invalid_snapshot")
        return {}


def save_vectors(
    path: Path,
    identity: str,
    dimension: int,
    normalization: str,
    entries: dict[str, tuple[float, ...]],
) -> None:
    """Atomic replacement leaves a previous complete snapshot intact after interrupted writes."""
    payload = VectorSnapshot(
        identity=identity,
        dimension=dimension,
        normalization=normalization,
        entries=entries,
        checksum=checksum(entries),
    ).model_dump_json()
    if len(payload.encode()) > 20_000_000:
        return
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=".vectors-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
