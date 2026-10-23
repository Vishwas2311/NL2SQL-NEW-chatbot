# Embedded graph migration - 2026-10-23

## Decision and implementation

User-authorized migration selects LadybugDB 0.21.2, embedded in the Python process,
with immutable on-disk graph projections. No graph daemon, cloud service, extension
or inference call is introduced. Python 3.13 Windows native execution was exercised.
Official references: https://docs.ladybugdb.com/concurrency/ and
https://docs.ladybugdb.com/client-apis/python/ .

The architecture review covered application/domain boundaries, every graph constructor,
metadata certification/build/publication/recovery, drift impact, planner, composite
compiler, independent SQL validation, bootstrap lifecycle, configuration, CLI subprocesses,
project agent instructions, dependency locks, CI/check hooks and existing tests.

NetworkX and its stubs are removed from pyproject, both application locks and the
application environment. Historical design references and dated generated analysis
artifacts are retained as historical evidence, not current executable dependencies.
The separate Graphify tool environment remains independent of application dependencies.

Application GraphTraversal is the typed boundary. LadybugGraph supplies frontier BFS
using bound Cypher values, filters allowed edges before traversal, and supports persisted
lineage queries. JoinGraph continues independent certification, temporal, cardinality,
same-endpoint ambiguity and six-edge checks. Composite compilation and independent SQL
validation use the same pinned topology through their separate policy checks.

Pure DirectedGraph replaces transient structural cycle checking, catalog validation,
drift dependency construction and impact reachability. These deterministic computations
remain free of native storage I/O. Authoritative metadata attributes remain in the signed
Pydantic catalog; graph files are rebuildable projections, not a new permission authority.

Runtime and standalone bootstrap own native resources. Initialization failures unwind
through ExitStack; retired bundles close graph handles after leases drain. Files are
catalog-digest named, built under an exclusive reservation into a unique temporary file,
transactionally populated, checkpointed and closed, then renamed and opened read-only.
Concurrent first builders wait up to 30 seconds. Existing files are never overwritten.
Read-only startup compares catalog identity, join topology and lineage topology.
Canonical artifact edge serialization preserves prior source-node ordering for recovery.
SQLite retains grants, approvals, sessions and the active pointer. Scheduling remains
external and disabled by default; discovery does not auto-certify or auto-publish.

## Agent and configuration review

AGENTS.md now reflects the explicitly approved LadybugDB dependency. No runtime agent
or graph-specific API key is required. Existing model/embedding/auth keys and SecretStr
handling remain unchanged. No global agent trust records, plugin hooks, credentials or
secret values were edited. Graphify and Archify outputs predate this migration and must
be regenerated before being presented as source-current architecture artifacts.

Central Settings adds graph_buffer_mb (64 MiB per handle, 32?1024 range) and optional
graph_native_dir. Windows wheel loading required approved OpenSSL 3 DLL provisioning;
tests use NL2SQL_TEST_GRAPH_NATIVE_DIR. A Git installation's DLL directory supplied the
local validation prerequisites; that machine-specific directory is not an application
default and does not qualify production packaging. Query threads are bounded to one.

## Validation

Initial broad run: 393 passed, eight explicit Redis tests skipped, one CLI subprocess
failure due to missing native DLL provisioning in its test environment. The CLI launcher
was corrected; focused CLI and policy rerun: nine passed. Native persistence, allowed-edge
filtering, exclusions, lineage, close/reopen, catalog mismatch, corruption, failed build
and concurrent first-build/read-only subprocess regressions: six passed including pure
policy cases. Final mandatory `python scripts/check.py` run completed successfully: 399 passed,
eight explicit Redis integration tests skipped, one pre-existing Starlette/httpx
deprecation warning, 89% branch-inclusive aggregate coverage. Ruff, formatting,
Pylint (10.00/10), strict Pyright (zero errors) and pre-commit all passed.
Full log: output/graph-migration-final-check.log. Dependency consistency: pip check passed.

## Measurements

Synthetic five-table/four-relationship catalog, 100 iterations, 64 MiB buffer setting:
join-resolution median 19.43 ms, p95 25.26 ms; build 756.68 ms; file 1,056,768 bytes.
Process peak working set 69,038,080 bytes, including Python/native/process overhead.
This is not a per-engine memory allocation or a process memory cap.

Additional synthetic chain topology measurements (20 six-edge traversals each):

| Tables | Relationships | Build seconds | Traversal median ms | p95 ms | File bytes |
|---|---|---|---|---|---|
| 100 | 99 | 1.01 | 16.51 | 24.89 | 3,186,688 |
| 1,000 | 999 | 15.32 | 125.85 | 300.81 | 4,354,048 |

Measurements ran with concurrent validation work on this laptop. They are observations,
not throughput, maximum-size, concurrent-user capacity or production acceptance claims.
The chain fixtures isolate topology/storage; they are not complete business catalogs.
Raw observations are in output/graph-benchmark.json and output/graph-scale-benchmark.json.

## Post-implementation architecture review and readiness

Dependency direction remains inward: native imports occur only in infrastructure.
The request path retains bound values, independent SQL authorization, signed capabilities,
read-only source execution, immutable catalog pins and current-grant reauthorization.
No UI content or integration changes, company Oracle connections or deployment occurred.

Local embedded storage is implemented and exercised. Production readiness remains
conditional: qualify exact Windows/native DLL packaging, real target VM concurrency,
resource budgets, crash/power-loss recovery, operational backups and Oracle/IAM/provider
contracts before deployment. Native crashes can affect the host API process.

Frontier BFS uses predecessor maps rather than retaining every full path. It still issues
one native query per frontier and sends allowed endpoint sets; the 1,000-table result
shows this as a scaling bottleneck. Benchmark representative authorized views and consider
a measured native recursive-query optimization before increasing supported workloads.
In-process locks serialize queries per handle. Each live bundle has a native buffer budget;
retained versions and multiple workers multiply resource costs. No in-place writer can
coexist with independent read-only workers on the same graph file.

A stale .building reservation after abrupt process death needs inspected maintenance.
Retired graph files require all-worker drain evidence before manual removal; local lease
counts do not authorize shared-file deletion. Filesystem-level permissions must restrict
the graph directory and DLL directory. No power-loss fault-injection, real Redis, Oracle,
Gemma, FAISS or corporate identity qualification is asserted by synthetic tests.

Deployment storage should be a qualified local filesystem outside synced OneDrive folders
or network shares. The source workspace location does not qualify durable database storage.

The existing known-answer workflow benchmark also passed all 46 synthetic cases
(37 eligible answers correct, nine intended rejection cases). It used scripted mock
plans, not an actual language model. End-to-end median was 962.48 ms and p95 2634.37 ms
under concurrent validation load; raw details are in output/graph-workflow-benchmark.json.
Windows CI now explicitly verifies and supplies its Git-distributed OpenSSL DLL directory.
The remote workflow was edited but not executed here; production should package/pin
its own approved native dependencies rather than rely on an unqualified runner image.

The independent local post-implementation review found no remaining blocking code
defects after its startup-race, immutable-file overwrite, path-memory, digest-order
and subprocess native-configuration findings were addressed. No cross-model review
was performed, as requested. Graph directories carry the existing .metadata-private
marker so project export exclusion recognizes their restricted contents.
