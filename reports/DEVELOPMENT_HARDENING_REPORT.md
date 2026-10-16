# V4.3 development hardening and completion report

## A. Overview

Implemented the authorized local development hardening in the existing backend. The original
frontend and numbered design pack were not edited. No company Oracle, hosted/private inference,
real embedding service, native FAISS, corporate SSO, deployment or remote push was performed.

Final verification: **scripts/check.py exited 0: 323 tests passed, 89% branch-inclusive coverage; Ruff/format, Pylint 10.00/10, strict Pyright and every pre-commit hook passed**. The historical baseline was 249 cases/89% coverage. The initial
baseline attempt in this turn overlapped edits and was not used as pristine baseline evidence.
Intermediate failures were retained in ignored logs and fixed; final evidence is authoritative.

## B. Before versus after

| Area | Before | After |
|---|---|---|
| Configuration | Separate environment-only and direct JSON construction | Explicit environment > selected dotenv > JSON > defaults; safe validation CLI; core/Oracle locks |
| Models | Disabled or private HTTP construction duplicated in factories | One registry/factory; scripted, private and separately gated synthetic hosted modes; output capabilities |
| Embeddings | Injectable in tests, absent from normal managed construction | Configured fake/local port/private HTTP, one compatibility identity across staging/publication/runtime |
| Search | Metric exact/BM25 and optional metric vectors | Typed source/column/dimension/view/relationship records and candidates; authorized structural context |
| Index work | Native results repeated a Python cosine scan; native request searched all keys | Native scan bounded to 80 overfetch/20 returned; no duplicate cosine; bounded caches and batches |
| Runtime builds | Expensive shared retrieval construction under a cache lock | Single-flight future with reserved references, expensive work outside the lock, bounded waits |
| Restart | Discovery/staging on every managed startup | Verify approved local snapshot; discovery remains administrative/scheduled or an explicit startup gate |
| Relationships | Physical FK evidence only | Explicit typed logical proposals, compatible grains/types/partitions and signed publication reviews |
| Operations | Limited readiness and timings | Authenticated component status, safe refresh attention events, graph/embedding/session/pool timings |

The architecture remains immutable Pydantic contracts, application services and typed adapters.
FastAPI delegates; deterministic SQLGlot compilation and independent capability validation remain.

## C. Exact added or modified implementation modules

Paths below are project-relative for portable handoff. Original numbered documentation/UI files
are excluded because this task did not change them. Existing unrelated `.gitignore` edits were preserved.

| Module | Change |
|---|---|
| backend/nl2sql/__main__.py | Explicit dotenv/config validation; safe optional-dependency failures |
| backend/nl2sql/api.py | Shared provider construction, configured encoder ownership, safe startup/storage errors, component readiness/auth timings |
| backend/nl2sql/bundle_build.py | Retrieval/encoder fingerprints and shared retrieval options |
| backend/nl2sql/catalog.py | Logical evidence checks; polynomial bounded ambiguity checks using NetworkX; graph timings |
| backend/nl2sql/certification.py | Explicit numeric precision/scale reconciliation; reviewed logical join proposals |
| backend/nl2sql/config.py | Deterministic loader, provider/retrieval/cache/startup configuration and validation |
| backend/nl2sql/database.py | SQLite integer bind bounds distinct from Oracle precision; query-pool queue timing |
| backend/nl2sql/domain.py | Certified precision/scale and logical join evidence contracts |
| backend/nl2sql/drift.py | Time-only/source dependency impact, correct semantic root types, no fictitious affected nodes |
| backend/nl2sql/embedding_cache.py | Added restricted bounded atomic JSON vector cache, compatibility/corruption/path guards |
| backend/nl2sql/embeddings.py | Added provider adapters, installed runtime registration, validation, deadlines/cancellation, batching/single-flight/LRU |
| backend/nl2sql/entity_lookup.py | Safe integral Decimal key handling and malformed-result rejection |
| backend/nl2sql/evaluation.py | Explicit injected-provider/model comparison seam; qualification labels |
| backend/nl2sql/load_evaluation.py | Added repeatable simultaneous-caller application measurements and separate tracing option |
| backend/nl2sql/managed_resources.py | Same configured encoder/provider in workflow/runtime; optional startup discovery; component readiness |
| backend/nl2sql/metadata_cli.py | Restricted review output; shared loader/providers; explicit selected dotenv through administrative operations |
| backend/nl2sql/metadata_config.py | Lazy optional Oracle imports for synthetic/core portability |
| backend/nl2sql/metadata_store.py | Distinct cross-process scheduler lease in addition to fenced refresh lease |
| backend/nl2sql/metadata_workflow.py | Encoder/retrieval configuration changes invalidate reuse; malformed catalogs still stage for review |
| backend/nl2sql/model.py | Shared transport, factories, output modes, strict role/tool/identity parsing, bounded retry/cancellation and hosted egress |
| backend/nl2sql/oracle.py | Safe readiness acquisition failure and cleanup |
| backend/nl2sql/oracle_discovery.py | Safe pooled acquire/release/rollback/drop failures |
| backend/nl2sql/planning.py | Decimal filters use certified precision/scale/output places rather than a global two-decimal rule |
| backend/nl2sql/ports.py | Sanitized component-readiness contract |
| backend/nl2sql/refresh.py | Scheduled dry-run overlap prevention and bounded safe attention logging |
| backend/nl2sql/retrieval.py | Typed schema search, per-partition synchronization, identifiers, budgets and bounded fusion; native/lexical isolation |
| backend/nl2sql/retrieval_evaluation.py | Added independent exact/BM25/graph/hybrid ablations and authored non-exact questions |
| backend/nl2sql/runtime_bundle.py | Lazy optional Oracle import and single-flight retrieval builds outside the cache lock |
| backend/nl2sql/search_metadata.py | Added typed certified hierarchical records, authorization/link pruning and general candidates |
| backend/nl2sql/service.py | Integer entity lookup through the full pipeline; controlled follow-ups and request-local timings/deadline |
| backend/nl2sql/sessions.py | Bounded lock waits, request deadlines and actual session contention timings |
| backend/nl2sql/telemetry.py | Scoped stage/deadline propagation and typed timing helpers |
| backend/nl2sql/vector_index.py | Bounded native overfetch/output |
| scripts/concurrency_benchmark.py | Added untraced latency plus a separately labeled traced-memory run |
| scripts/retrieval_benchmark.py | Retrieval-only ablations alongside existing scripted workflow comparison |
| export_project_to_txt.py | Detect copied private JSON regardless of filename extension |
| tests/test_export_project.py | Private `.txt` payload regression |
| tests/test_hardening.py | Added audit, integration, integer-key E2E, lifecycle, session, retrieval and concurrency regressions |
| tests/test_hardening_provider_contracts.py | Added fake transport, egress, cancellation, cache, installed-provider and core-only dependency contracts |
| tests/test_model_comparison.py | Additional focused comparison-runner regression with two independent scripted providers |

Other deliverables: `.env.example`, `config/office.example.json`, `requirements-core.lock`,
`requirements-oracle.lock`, `DEVELOPMENT_HARDENING_RUNBOOK.md`, README.md, the four tracking documents,
this report and current quality/benchmark/portability/preservation evidence. The text export is regenerated.
The existing benchmark/schema-evolution scripts and compiler/SQL-validator operators were reused.

## D. Model and embedding integration

Model modes: disabled; deterministic scripted; private OpenAI-compatible HTTP; separately authorized
hosted HTTP. Trusted code can register another adapter. JSON-schema, JSON-object and explicitly
selected strict text-JSON responses produce the same QueryPlan. Missing/wrong roles, modern or
legacy tool calls, wrong IDs, oversized/incomplete replies and invalid plans reject safely. Only
bounded transient availability failures retry. Direct provider cancellation is tested.

Hosted mode checks configured synthetic-only authorization, exact HTTPS host and assembled catalog
classification before sending. Private mode retains private-address and verified-TLS checks.
The configuration validation command does not execute inference or Oracle queries.

Embedding modes: disabled, deterministic synthetic fake, explicitly registered installed local
runtime and approved private HTTP. No model or weights were downloaded. The installed-runtime
registration is a tested port, not qualification of an unspecified office SDK/model.
Model/version/dimension/normalization identity participates in cache and signed bundle compatibility.
Normal CLI stage/publish/monitor and managed startup use that configured provider, including selected
dotenv configuration. Partial/late/nonfinite/zero/wrong-sized responses never enter the cache.
The cache is bounded and coalesces duplicate concurrent content; optional disk snapshots require
marked restricted storage. Cache corruption rebuilds, while signed manifests remain authoritative.

## E. Retrieval improvements

Certified catalog mappings generate domain/table/column/dimension/metric/alias/view/relationship,
date/grain and business-term records. Each carries stable identity, parent/links, provenance, version,
authorized metric dependencies and embedding text. Dictionary-only additions remain unsearchable.
Table/column/view identifiers and simultaneous BM25 searches are tested explicitly.

The existing metric-planning interface stays compatible. General schema candidates use the separate
typed schema-search method; model context includes authorized structural evidence and certified
joins/dimensions with a deterministic byte budget. Existing optional vectors rank metric documents;
schema/source records are searched lexically. Compiler graph/policy validation remains independent.

39 authored retrieval questions; no model calls; K=10.

| Mode | Precision@10 | Recall@10 | Metric source-table recall | Authorization violations |
|---|---:|---:|---:|---:|
| exact_only | 87.18% | 87.18% | 87.18% | 0 |
| exact_bm25 | 94.39% | 100.00% | 100.00% | 0 |
| graph_filtered | 94.39% | 100.00% | 100.00% | 0 |

Context assembly counts each encoded evidence entry once instead of repeatedly serializing the
entire context/schema. The same deterministic budget/truncation tests and business goldens apply.

These authored synthetic regression questions are not enterprise-held-out accuracy evidence.
No approved real encoder was supplied, so real hybrid promotion is unmeasured. Fake/native-binding
contract tests do not establish semantic encoder or native FAISS quality.

## F. Index and concurrency measurements

| Simultaneous callers | Requests/correct | p50 ms | p95 ms | Requests/s | Pool queue p95 ms | Traced peak bytes (separate run) |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 3/3 | 18.93 | 18.93 | 45.63 | 0.03 | 404,358 |
| 10 | 30/30 | 144.32 | 158.47 | 63.99 | 0.02 | 1,198,428 |
| 25 | 75/75 | 472.57 | 697.75 | 46.30 | 0.03 | 1,753,037 |
| 50 | 150/150 | 1446.62 | 1469.59 | 34.11 | 0.03 | 2,890,158 |

Latency and throughput are from an untraced application-service run; incremental Python peak
allocation during requests is measured in a separate traced run (not total process RSS).
Each level issues three fresh-session requests per simultaneous
caller against the same independently expected rows. This bypasses HTTP/network authentication
and rate-limit overhead; it is not a corporate capacity/SLO acceptance test. Session contention is
measured directly. No asynchronous rewrite, new server or vector database was introduced.

Native search is capped at 80 examined neighbors/20 native outputs and reauthorized before fusion;
Python cosine runs only without a native index. Existing immutable active indexes remain available
while a candidate builds. Shared builds coalesce outside the resource lock, with reserved references,
and retired resources close after leases drain. Disk cache/history retention remains an operator policy.

## G. Oracle and graph support

Oracle adapter/discovery tests use synthetic fake drivers. Ready/acquire/release/rollback/drop
errors are sanitized. Core-only startup/import and explicit missing-driver failures are tested.
No company connection or real Oracle transaction was attempted.

Logical relationships without FKs require explicit review reference, effective version, ordered
column pairs/types, grains, tenant partitions, direction/cardinality and temporal evidence. Physical
type/grain reconciliation still applies, and publication still requires configured signed review roles.
Imports and discovered names cannot authorize a relationship. Duplicate/ambiguous/type/partition/grain
contracts reject; fanout and current-only historical traversals remain blocked.
NetworkX ambiguity checking uses at most six alternative breadth-first path searches, replacing
unbounded simple-path enumeration. General SCD2 intervals remain unsupported without certified semantics.

## H. Security

Authentication, per-turn authorization, tenant/region/metric scope, ownership, capability expiry,
query proof and independent SQL validation remain. No browser identity, metadata description,
prior message or model response can grant access. All filter values remain bound. Money output
uses Decimal strings; synthetic storage remains integer minor units.

Private review output cannot escape restricted storage, and the exporter recognizes copied private
payloads even in `.txt`. Model/embedding errors and local storage/startup failures omit raw provider
details. Readiness/logging do not expose endpoints, secrets, prompts or binds. Known revocations and
quarantines remain effective across pinning, publication and rollback. Installed Ponytail read-first,
smallest-complete-change, risky-test and review guidance was applied. Hook activation is unverified;
no trust records were changed and no lifecycle-hook activation is claimed.

## I. Tests and evidence

- Full suite: **323 passed**, one upstream warning, **316.89s**; **89%** branch-inclusive coverage.
- All six quality gates passed; no thresholds, tests or assertions were weakened.
- 74 added cases were included in the full run, supplementing the original 249-test baseline.
- One additional focused comparison-runner regression passed afterward (1/1 in 24.36s): two independent scripted providers each passed 46/46 workflows. Application code did not change after the full quality run.
- Scripted business workflows: **46/46** scenarios; **37/37** independent numerical results and **9/9** safe outcomes.
- Workflow timings under tracing: p50 **364.22ms**, p95 **699.40ms**; these are not real-model inference times.
- Schema evolution: **30/30** expected results; unchanged/row-only changes do not rebuild; unapproved columns gain no permissions.
- Real clean-install loopback HTTP: health/readiness/chat/components and owned session list/load/delete passed.
- Both original and clean core-only environments passed pip check. No Oracle driver is installed in the clean environment.
- Concurrent BM25 correctness passed at 1/10/25/50 workers; actual application-load measurements are reported above.
- Evidence: reports/quality-hardening.txt, benchmark.json, retrieval.json, schema-evolution.json, concurrency.json,
  api-smoke-hardening.json, portability-hardening.json and preservation-hardening.json.


The single observed warning is upstream Starlette/httpx TestClient deprecation. The approved pinned
stack was retained; no unsupported httpx2 migration was added. Mandatory security/compiler/API,
publication/rollback/revocation and preservation tests remain enabled. No thresholds or assertions
were weakened. The original document directories have no Git worktree changes. All six original UI
files match original byte hashes. Original documents have pre-existing CRLF working copies versus
their LF manifest/index; all 36 numbered content hashes match after LF normalization. They were not rewritten.

## J. Portability and verified PowerShell

Clean Windows Python 3.13.16 environment: 22 exact pinned core packages installed, editable project
installed, no Oracle driver, disabled-model synthetic query returned both expected region totals,
and pip check passed. Optional Oracle dependencies have a separate exact lock. No weights, company
credentials or hidden local runtime were required. Safe missing-Oracle-driver selection was verified.

Commands executed from this project root:

```powershell
.\.venv\Scripts\python.exe scripts/check.py
.\.venv\Scripts\python.exe scripts/benchmark.py
.\.venv\Scripts\python.exe scripts/retrieval_benchmark.py
.\.venv\Scripts\python.exe scripts/schema_evolution.py
.\.venv\Scripts\python.exe scripts/concurrency_benchmark.py
.\.venv\Scripts\python.exe -m venv .local/hardening-clean-venv
.\.local\hardening-clean-venv\Scripts\python.exe -m pip install -r requirements-core.lock
.\.local\hardening-clean-venv\Scripts\python.exe -m pip install --no-deps -e .
.\.local\hardening-clean-venv\Scripts\python.exe -m nl2sql validate-config --settings .local/hardening-clean-smoke/data/settings.json --env-file .env.example
.\.local\hardening-clean-venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe export_project_to_txt.py
```

The demo settings used above were generated by the synthetic initializer; they are ignored private
runtime state. The runbook provides fresh-directory initialization commands for transfer. Git must
be on PATH for pre-commit; no absolute personal path was embedded into application source/config examples.

## K. Remaining limits by category

**Implemented and locally verified:** configuration/provider/cache contracts, normal configured
embedding wiring, hierarchical lexical metadata, safe context, bounded retrieval/build work,
synthetic logical evidence/publication, audit fixes, request pinning and deterministic execution.

**Requires approved environment qualification:** company Oracle/NUMBER/TIMESTAMP/privileges/VPD,
installed embedding SDK/model and native FAISS, real private/hosted inference accuracy/TLS/capacity,
corporate identity/SSO/rotation/revocation and enterprise monitoring/SLO/storage approvals.

**Intentionally unsupported:** unrestricted SQL/repair fallback, arbitrary formulas/windows/CTEs,
general SCD2/effective-interval joins, new LAG/LEAD/running-total/period-comparison semantics and
existing unsupported average/ratio sort/HAVING. Business semantics were not guessed.

**Operational/unmeasured:** actual HTTP load, disconnect-to-provider cancellation integration,
forced interruption inside an unspecified installed Python model runtime, approved disk-history/cache
retention, company-specific physical freshness/startup gate and scheduler/alert ownership. Provider
cancellation/deadline contracts are tested; no claim of terminating arbitrary external native work.

**Pre-existing preservation detail:** numbered documents differ from their original manifest in line
endings only. Their contents and original UI hashes are verified, and those directories were untouched.

## L. Office handoff checklist — not executed here

1. Transfer source, exact locks, sanitized examples, runbook and evidence; exclude ignored private state.
2. Provision company-approved restricted storage and secret/environment injection.
3. Supply steward-certified metrics, units/scales, dimensions, grains, calendars, physical mappings and logical evidence.
4. Configure trusted review keys/admin identities; stage, review, sign and publish a candidate through the existing lifecycle.
5. Have the DBA qualify separate discovery/query accounts, read-only grants, VPD/context reset and resource controls.
6. Register the existing installed encoder runtime or approve its private endpoint; qualify actual output/version compatibility.
7. Qualify real inference on held-out business questions before enabling flexible planning or considering hosted egress.
8. Integrate corporate identity, live revocation and monitoring; select physical freshness/startup and external scheduler policies.
9. Run representative Oracle, inference, HTTP load, cancellation, recovery and retention acceptance checks.
10. Obtain release approval before any deployment, publication or remote push.
