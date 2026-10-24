# SurrealDB migration verification — 24 October 2026

LadybugDB has been replaced in both runtime graph and optional vector adapters by
the pinned SurrealDB Python SDK and embedded core, both reporting version 2.0.0.
The development environment no longer contains LadybugDB. Driver stubs, native DLL
directory hooks, buffer settings and Windows CI OpenSSL prerequisites were removed.
No UI assets, authoritative query/session rows or company systems were changed.

## Design retained

SQLite still owns metadata, approvals and sessions; Redis only coordinates admission.
The compiler, independent SQL validator, signed capabilities, Decimal formatting,
current-grant checks and read-only query adapters keep their existing contracts.

Verified immutable `.surreal.json` graph artifacts are atomically published from the
approved catalog. Each runtime handle creates an independent embedded `mem://` store,
avoiding SurrealKV's exclusive persistent-directory lock across API/monitor processes.
Native links drive authorized frontier traversal and lineage. Per-scope exact-cosine
search binds allowed keys before ordering/limiting. Old `.lbdb` files remain untouched.

The review exposed a startup compatibility gap for lexical-only signed bundles. Runtime
now verifies the signed search fingerprint before native allocation, including when
embeddings are disabled. Tests prove obsolete fingerprints and old candidate signatures
are rejected, prior authority is unchanged and a newly signed publication restores service.

## Completed verification

| Check | Result |
|---|---|
| `python scripts/check.py` | Exit 0 |
| Ruff correctness and formatting | Passed |
| Pylint | 10.00/10 |
| Strict Pyright | 0 errors, warnings or information messages |
| Full pytest suite | 484 passed; 9 Redis integration tests skipped; 1 existing dependency deprecation warning |
| Branch-inclusive coverage | 90% |
| Pre-commit, all files | All three automatic hooks passed |
| `pip check` | No broken requirements |
| Binary-only Windows core dependency resolution | All 34 resolved packages explicitly pinned |
| Real native migration cases | Passed, including two processes, fresh concurrent publication, restart, corrupted snapshots, incomplete native graphs, filtered traversal, vector filtering/ties, 20 concurrent vector calls, independent handles and cleanup |
| Clean-path subprocess | Graph and vectors passed without external graph/OpenSSL directory configuration; LadybugDB was not imported |
| Synthetic workflow benchmark | 46/46 cases passed; join correctness true |
| Direct synthetic service load | 20 simultaneous callers, 60/60 correct responses, zero errors; observed p95 approximately 2.87 seconds |

The service load uses disabled inference and one synthetic principal; it bypasses HTTP
admission. Existing two-route HTTP contract tests separately exercise twenty identities,
bounded admission, responses, follow-ups and session ownership. These are different tests,
not evidence of twenty simultaneous real SLM generations. Timing stages overlap and
must not be added together. [Machine-readable benchmark](surrealdb-validation-2026-10-24.json).

## Upgrade and remaining qualification

Use [the migration guide](../docs/SURREALDB_MIGRATION.md). Remove obsolete graph JSON/env
settings and stage/review/sign a fresh managed publication; do not rewrite old approvals.
The retrieval memory setting is an admission estimate, not a SurrealDB allocator/RSS cap.

Real Redis was not available in this run. Company Oracle, corporate identity, actual
SLM/encoder accuracy, office RSS/recovery and macOS/Linux execution remain unqualified.
CI jobs for those supported platforms are retained but were not executed here.
Python's linked SQLite remains 3.50.4 on this development machine; the office SQLite
preflight remains enabled and graph replacement does not resolve that independent issue.
No deployment, company connection, weights download or remote push was performed.
