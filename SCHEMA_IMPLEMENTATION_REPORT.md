# V4.3 implementation status

The governed local/synthetic lifecycle is implemented in the existing backend. Oracle discovery and
execution adapters are prepared and contract-tested; live corporate integration is not qualified.
Existing UI assets and original numbered designs are preserved. Nothing was deployed or published
outside the local synthetic metadata store.

| Phase | Status | Evidence / qualification |
|---|---|---|
| 0 Baseline | Complete | 194 tests and all original quality gates passed before upgrade |
| 1 Oracle-first adapters | Partial | Bound dictionary discovery, raw names/NUMBER/keys/budgets tested; no live Oracle |
| 2 Bootstrap | Complete (local) | One synthetic command creates candidate; physical-only and file paths supported |
| 3 Index/graph builders | Partial | Automatic FTS5/BM25/NetworkX; optional versioned vectors/FAISS adapter; native/model run blocked |
| 4 Drift/impact | Complete (local) | Normalized changes, transitive dependencies and selective quarantine |
| 5 Governance | Complete (local) | Configured admin/reviewer signatures, three roles, tamper rejection; corporate trust rollout open |
| 6 Runtime bundle | Complete (local) | Full preparation, durable CAS, pinned requests, draining, recovery and revocation tests |
| 7 Schema-aware SQL | Partial | Quoted mappings, typed policies/entities/units and bounded deterministic operators; extended temporal/windows absent |
| 8 Refresh/rollback | Complete (local) | Disabled external scheduler, retries/leases, compatible rollback without old grants |
| 9 Integration/testing | Partial | Real synthetic CLI/API/HTTP, security/evolution tests; corporate Oracle/Gemma/SSO blocked |
| 10 Performance/review | Partial | Measured workflow/build/query evidence and Ponytail review; real hybrid/production load open |

Discovery -> physical evidence -> explicit business/security mappings -> signed review -> graph/search/
compiler/runtime readiness -> atomic publication. A model/comment or imported approved flag cannot
skip certification. One bundle version pins planning through response. New objects grant no access.
Revocations invalidate active work and rollback cannot restore them. All values remain bound and
financial results use exact Decimal strings with explicit divisor/output precision.

Run [the tested PowerShell workflow](ORACLE_BOOTSTRAP_RUNBOOK.md). It includes pinned installation,
checks, bootstrap, review/approval/publication, serve, status, sync, disabled-by-default scheduling and
rollback. Oracle commands are marked separately as guard/adapter-tested and not live-qualified.
For a new column, stage/inspect impacts, revise only owner-approved mappings/grants, re-sign and
publish; compatible supported mappings need no Python rewrite.

Final checks: 249 tests passed, 89% branch-inclusive coverage; Ruff lint/format, Pylint 10.00/10,
strict Pyright and pre-commit passed. Pinned dependency audit found no known vulnerabilities.
See SCHEMA_EVOLUTION_TEST_RESULTS.md and reports/quality-check-v43.txt for evidence.
Local benchmark: 30/30 correct template answers; p50 40.07 ms/p95 50.32 ms; 346.26 ms initial build.
The independent 46-case workflow benchmark passes all cases using scripted plans. Lexical remains
default; FAISS native execution/approved embeddings and Gemma accuracy were not measured.

Supported/unsupported SQL is explicit in SQL_COMPLEXITY_REQUIREMENTS.md. General SCD2 interval
joins, MoM/YoY, RANK, LAG/LEAD and running totals are not implemented. No business contract was
invented to claim them. Oracle NUMBER/date/cancellation/context behavior is exercised through injected
driver contracts; real grants, VPD, cost plans, pooling and operational SLOs need DBA qualification.

Ponytail official 5.2.0 is installed and enabled; coding/audit/review skills were applied manually.
Configured hook hashes exist, but there is no /hooks/runtime execution evidence. Hook activation is
not claimed. No trust records were edited, plugin reinstalled or subagents created.

Remaining release gates: authorized Oracle network/owners/credentials, verified business/security
catalogs, company identity and trust distribution, approved Gemma checkpoint/endpoint and embedding
model, native FAISS approval/benchmark if justified, supported new SQL requirements, deployment/HA/
backup/alerts/load/penetration/privacy/license reviews and release approval. This is not an enterprise
production-readiness claim.
