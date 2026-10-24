"""Local-folder embeddings load offline without application registration code."""

import json
import sys
from types import SimpleNamespace

import pytest
from nl2sql.domain.models import Failure
from nl2sql.infrastructure.retrieval.embeddings import build_embedding
from nl2sql.settings import Settings


@pytest.fixture
def local_model(tmp_path, monkeypatch):
    path = tmp_path / "local MiniLM"
    path.mkdir()
    (path / "modules.json").write_text(
        json.dumps([{"type": "sentence_transformers.models.Transformer", "path": ""}])
    )
    (path / "config.json").write_text('{"model_type":"bert"}')
    (path / "model.safetensors").write_bytes(b"synthetic model bytes")
    calls = []

    class Model:
        def __init__(self, directory, **options):
            calls.append((directory, options))

        def get_embedding_dimension(self):
            return 2

        def encode(self, texts, **_options):
            return SimpleNamespace(tolist=lambda: [[3.0, 4.0] for _ in texts])

    monkeypatch.setitem(
        sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=Model)
    )
    return path, calls


def test_path_only_loads_offline_and_tracks_model_content(local_model):
    path, calls = local_model
    configuration = Settings(embedding_mode="local", embedding_local_path=path)
    encoder = build_embedding(configuration)
    assert encoder.encode(("fictional metric",)) == ((0.6, 0.8),)
    assert encoder.settings.embedding_dimension == 2
    assert calls[0][0] == str(path.resolve())
    assert calls[0][1]["local_files_only"] is True
    assert calls[0][1]["trust_remote_code"] is False
    assert calls[0][1]["model_kwargs"]["use_safetensors"] is True
    identity = encoder.identity
    encoder.close()
    (path / "model.safetensors").write_bytes(b"different synthetic model")
    changed = build_embedding(configuration)
    assert changed.identity != identity
    changed.close()


def test_local_model_rejects_custom_code_and_wrong_dimension(local_model):
    path, calls = local_model
    with pytest.raises(ValueError, match="dimension"):
        build_embedding(
            Settings(embedding_mode="local", embedding_local_path=path, embedding_dimension=3)
        )
    calls.clear()
    (path / "modules.json").write_text('[{"type":"custom.Code","path":""}]')
    with pytest.raises(ValueError, match="module"):
        build_embedding(Settings(embedding_mode="local", embedding_local_path=path))
    assert not calls


def test_missing_runtime_and_legacy_weights_fail_safely(local_model, monkeypatch):
    path, calls = local_model
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    configuration = Settings(embedding_mode="local", embedding_local_path=path)
    with pytest.raises(Failure) as missing:
        build_embedding(configuration)
    assert missing.value.code == "EMBEDDING_DEPENDENCY"
    (path / "model.safetensors").unlink()
    (path / "pytorch_model.bin").write_bytes(b"never unpickle this")
    with pytest.raises(Failure) as legacy:
        build_embedding(configuration)
    assert legacy.value.code == "EMBEDDING_MODEL_FORMAT"
    assert not calls
