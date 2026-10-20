"""Stable catalog and authorization fingerprints; no storage access."""

import hashlib
import json

from nl2sql.domain.models import Catalog, Principal


def digest(value: str) -> str:
    """Stable non-secret provenance fingerprint."""
    return hashlib.sha256(value.encode()).hexdigest()


def catalog_hash(catalog: Catalog) -> str:
    """Canonical snapshot hash independent of file whitespace."""
    return digest(json.dumps(catalog.model_dump(mode="json"), sort_keys=True))


def grant_digest(principals: tuple[Principal, ...]) -> str:
    """Changes to data or metric grants are part of the version contract."""
    return digest(
        json.dumps(
            [item.model_dump(mode="json") for item in sorted(principals, key=lambda user: user.id)],
            sort_keys=True,
        )
    )
