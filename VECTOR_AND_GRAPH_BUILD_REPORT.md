# Index and graph report

Default: exact aliases, scope-partitioned SQLite FTS5/BM25 and NetworkX. Search documents derive
from certified labels/aliases/definitions/domain, approved table/column descriptions and view IDs.
Only metric-granted metadata enters each partition. Customer rows are never embedded.

EmbeddingProvider injection builds versioned vectors with dimension/finite-value and cumulative
memory checks. Hybrid lexical/cosine rank fusion falls back to lexical after safe encoder failures.
Catalog, source/domain, metric IDs, grant partition and backend accompany vector entries.

FaissVectorIndex implements approved lazy normalized IndexFlatIP and is wired through Retriever,
BundleBuilder and RuntimeFactory via vector_factory. Backend identity enters the artifact manifest.
FAISS and NumPy have NOT been installed or executed. A fake native binding tests approval-before-
import, array shape/dtype, normalization, dimensions and permissions. This is adapter evidence only.
No approved encoder or actual hybrid benchmark exists; lexical remains default.

Qualification requires the same versioned encoder/vector_factory in the builder and runtime, the
paired workflow evaluation, business-result/rejection/latency/memory comparisons and signed review.
No command downloads a model or silently enables vectors. Optional dependencies need approval.

Official reference: [FAISS exact indexes/cosine normalization](https://github.com/facebookresearch/faiss/wiki/Faiss-indexes).
Local measurements: reports/benchmark.json, reports/retrieval.json, reports/schema-evolution.json.
Scripted/toy evidence is explicitly distinct from real model accuracy.
