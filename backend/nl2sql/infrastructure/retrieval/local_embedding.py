"""Offline CPU Sentence Transformers loader for approved local text models."""

import hashlib
import importlib
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

from pydantic import BaseModel, TypeAdapter

from nl2sql.domain.models import Failure


class _Array(Protocol):
    def tolist(self) -> list[list[float]]:
        """Cross the optional NumPy boundary using ordinary Python values."""
        ...


class _Model(Protocol):
    def get_embedding_dimension(self) -> int | None:
        """Report the saved model's output shape."""
        ...

    def encode(
        self,
        sentences: list[str],
        *,
        batch_size: int,
        show_progress_bar: bool,
        convert_to_numpy: bool,
    ) -> _Array:
        """Encode text locally without an HTTP model service."""
        ...


class _SavedModule(BaseModel):
    type: str
    path: str


def model_digest(path: Path) -> str:
    """Bind cache/signature identity to files, not a mutable folder name."""
    if not path.is_dir():
        raise ValueError("Select an existing local embedding model directory")
    fingerprint = hashlib.sha256()
    count = size = 0
    entries: list[Path] = []
    for entry in path.rglob("*"):
        entries.append(entry)
        if len(entries) > 2000:
            raise ValueError("Local embedding model exceeds its file budget")
    for file in sorted(entries):
        if file.is_symlink():
            raise ValueError("Local model files must not be symbolic links")
        if not file.is_file():
            continue
        count += 1
        size += file.stat().st_size
        if count > 2000 or size > 2_000_000_000:
            raise ValueError("Local embedding model exceeds its file budget")
        fingerprint.update(file.relative_to(path).as_posix().encode() + b"\0")
        with file.open("rb") as source:
            while chunk := source.read(1_048_576):
                fingerprint.update(chunk)
        fingerprint.update(b"\0")
    return fingerprint.hexdigest()


class LocalEmbedding:
    """Load standard Transformer/Pooling/Normalize modules and safetensors only."""

    def __init__(self, path: Path, batch_size: int) -> None:
        path = path.resolve()
        self.version = model_digest(path)
        modules_path = path / "modules.json"
        if not modules_path.is_file() or modules_path.stat().st_size > 100_000:
            raise ValueError("A saved Sentence Transformers modules.json is required")
        modules = TypeAdapter(list[_SavedModule]).validate_json(modules_path.read_bytes())
        allowed = {
            "sentence_transformers.models.Transformer",
            "sentence_transformers.models.Pooling",
            "sentence_transformers.models.Normalize",
            "sentence_transformers.base.modules.transformer.Transformer",
            "sentence_transformers.sentence_transformer.modules.pooling.Pooling",
            "sentence_transformers.base.modules.normalize.Normalize",
        }
        if not 1 <= len(modules) <= 8:
            raise ValueError("Unsupported local model modules")
        for module in modules:
            if module.type not in allowed or not (path / module.path).resolve().is_relative_to(
                path
            ):
                raise ValueError("Unsupported local model module or path")
        if not any(path.rglob("*.safetensors")):
            raise Failure(
                "EMBEDDING_MODEL_FORMAT",
                "Select an approved saved text model with safetensors weights; "
                "pickle weights are not loaded.",
                "invalid",
            )
        try:
            constructor = cast(
                Callable[..., _Model],
                importlib.import_module("sentence_transformers").SentenceTransformer,
            )
        except ImportError:
            raise Failure(
                "EMBEDDING_DEPENDENCY",
                "Install requirements-embeddings-windows.lock using install_office.py.",
                "unavailable",
            ) from None
        self._model: _Model | None = constructor(
            str(path),
            device="cpu",
            local_files_only=True,
            trust_remote_code=False,
            token=False,
            model_kwargs={"use_safetensors": True, "local_files_only": True},
            config_kwargs={"local_files_only": True},
            processor_kwargs={"local_files_only": True},
        )
        dimension = self._model.get_embedding_dimension()
        if dimension is None or not 1 <= dimension <= 4096:
            raise ValueError("Invalid local model embedding dimension")
        if model_digest(path) != self.version:
            raise ValueError("Local model changed while loading; use an immutable model folder")
        self.dimension = dimension
        self.batch_size = batch_size

    def encode(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        """ManagedEncoder applies deadline, input, shape, finite-value and cache checks."""
        if self._model is None:
            raise ValueError("Local embedding model is closed")
        return tuple(
            tuple(row)
            for row in self._model.encode(
                list(texts),
                batch_size=self.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
            ).tolist()
        )

    def close(self) -> None:
        """Release this process's owned model after request leases drain."""
        self._model = None
