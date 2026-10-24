"""Exercise optional native CPU loading with tiny random weights, never Hub downloads."""

import json
import math
import os
import subprocess
import sys

import pytest
from nl2sql.infrastructure.retrieval.embeddings import build_embedding
from nl2sql.infrastructure.retrieval.vector_index import SurrealVectorIndex
from nl2sql.settings import Settings


def test_offline_saved_model_encodes_and_reopens_in_fresh_process(tmp_path, monkeypatch):
    for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY"):
        monkeypatch.setenv(name, "1")
    transformers = pytest.importorskip("transformers")
    st = pytest.importorskip("sentence_transformers")
    from sentence_transformers.base.modules import Normalize, Transformer
    from sentence_transformers.sentence_transformer.modules import Pooling

    source = tmp_path / "synthetic-bert"
    source.mkdir()
    vocabulary = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]", "fictional", "loan", "metric"]
    (source / "vocab.txt").write_text("\n".join(vocabulary), encoding="utf-8")
    tokenizer = transformers.BertTokenizer(
        vocab={word: index for index, word in enumerate(vocabulary)}
    )
    tokenizer.save_pretrained(source)
    configuration = transformers.BertConfig(
        vocab_size=len(vocabulary),
        hidden_size=8,
        num_hidden_layers=1,
        num_attention_heads=2,
        intermediate_size=16,
        max_position_embeddings=32,
    )
    transformers.BertModel(configuration).save_pretrained(source, safe_serialization=True)
    transformer = Transformer(
        str(source),
        model_kwargs={"local_files_only": True},
        processor_kwargs={"local_files_only": True},
    )
    model = st.SentenceTransformer(modules=[transformer, Pooling(8), Normalize()], device="cpu")
    path = tmp_path / "saved model"
    model.save(str(path), create_model_card=False)
    settings = Settings(embedding_mode="local", embedding_local_path=path)
    encoder = build_embedding(settings)
    assert encoder is not None
    try:
        vectors = encoder.encode(("fictional loan", "metric"))
        assert len(vectors) == 2 and all(len(vector) == 8 for vector in vectors)
        assert all(math.isfinite(value) for vector in vectors for value in vector)
        assert sum(value * value for value in vectors[0]) == pytest.approx(1.0)
        identity = encoder.identity
        index = SurrealVectorIndex((("fictional-loan", vectors[0]), ("metric", vectors[1])))
        try:
            assert index.search(vectors[0], {"fictional-loan"})[0][0] == "fictional-loan"
        finally:
            index.close()
    finally:
        encoder.close()
    code = """
import json, sys
from pathlib import Path
from nl2sql.settings import Settings
from nl2sql.infrastructure.retrieval.embeddings import build_embedding
encoder = build_embedding(Settings(embedding_mode='local', embedding_local_path=Path(sys.argv[1])))
try:
    print(json.dumps({'identity': encoder.identity, 'vector': encoder.encode(('fictional loan',))[0]}))
finally:
    encoder.close()
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(path)],
        env=os.environ.copy(),
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    reopened = json.loads(result.stdout.splitlines()[-1])
    assert reopened["identity"] == identity
    assert reopened["vector"] == pytest.approx(vectors[0], abs=1e-6)
