# Architecture remediation — 24 October 2026

This records the first remediation snapshot. Subsequent 100K configuration, separate
inference admission and verification are recorded in the
[office qualification update](office-qualification-update-2026-10-24.md).

The architecture-review fixes are implemented in the current working folder. The modular
monolith and its existing database responsibilities are retained. This is preparation for a
later office transfer; no transfer, deployment, company connection or Git push was performed.

This report follows the 16 numbered findings in
[the original review](final-application-architecture-review-2026-10-24.md). That review remains
historical evidence. The current configuration, walkthrough and operating guides describe
the resulting implementation.

## Findings and disposition

| Finding | Implementation / decision | Evidence |
|---|---|---|
| 1. Persistent upgrades | Ordered transactional SQLite upgrades to `user_version=3`; explicit plan/message/bundle formats; legacy metadata identity and timestamps preserved; unknown future versions reject safely. | `infrastructure/storage.py`, `infrastructure/metadata/store.py`, `infrastructure/sessions.py`, `domain/metadata.py`; `tests/integration/test_storage_upgrades.py` exercises hand-created legacy databases, read-only reads, backup/restore, future formats and payload identity. |
| 2. Retrieval resource bounds | Count metric **and** schema text across distinct grant partitions before indexes are allocated. Enforce text, partition, vector-component and nominal native-buffer ceilings before native vector allocation. Keep grant isolation. | `infrastructure/retrieval/lexical.py`; `tests/unit/test_retrieval_budgets.py`. These are per-retriever bounds, not a measured process/VM RSS guarantee. |
| 3. Adoption deadlines | Start the application deadline before authentication, bound reload-lock waiting and graph-reservation waiting, inherit it in nested chat, and close/reject late-built candidates before activation. | `api/app.py`, `bootstrap/runtime.py`, `infrastructure/graph.py`; `tests/integration/test_request_adoption_budget.py`. Prefer a controlled drain/reload window initially. Arbitrary native calls cannot be forcibly stopped by a Python deadline. |
| 4. Typed clarification | `PlanningDecision.outcome` accepts `QueryPlan` or bounded `ClarificationRequest`; application-owned wording; suggested metrics must be authorized/retrieved; clarification runs no SQL. | `domain/planning.py`, model adapters, `application/chat.py`; conversation and HTTP model-contract tests. |
| 5. General follow-ups | Persist one bounded pending question and previous typed plan with catalog/scope identity. Supply only compatible, currently authorized context. Clear stale context and allow a new complete question. Reauthorize execution and history every turn. | `application/context.py`, `application/chat.py`, sessions adapter; `test_planning_conversations.py`, security/session regression suites. |
| 6. Twenty-user evidence | Exercise both HTTP chat contracts with 20 distinct identities, controlled slow planning and a simultaneous burst; then templates, deterministic follow-ups and owned history. Active work is bounded; excess requests receive 429 and `Retry-After`. | `tests/contracts/test_twenty_user_workload.py`. Real SLM throughput/accuracy and real Oracle remain external qualification requirements. |
| 7. Embedding-cache hot path | Query misses update bounded RAM only. Preparation explicitly checkpoints selected **metadata** vectors; snapshot copying occurs under the lock, serialization/disk writes outside it. Snapshot entry count accounts for dimension; optional cache failure is disposable. | `infrastructure/retrieval/embeddings.py`, bootstrap/metadata preparation; cache persistence and blocking-writer regression tests. No query text/results are deliberately selected for disk persistence. |
| 8. Demo routing / false rejection | Remove the synthetic fallback report dictionary from generic orchestration; reuse catalog templates. Extract routing, support catalog dimensions in deterministic grouping and correct the write-command prefilter. Read-only “Update me…” and “Drop in…” phrases reach planning. | `application/routing.py`, `application/chat.py`; conversation and workflow tests. Compiler, independent SQL validation and read-only execution remain the security boundary. |
| 9. Mandatory office encoder | Office supports disabled embeddings. The default example uses exact aliases/FTS5/BM25 plus Ladybug graph, with persistent embedding caching disabled. Optional approved private HTTP embeddings still automatically generate Ladybug vectors. | `cli/office.py`, `config/office.example.json`, `config/office.env.example`; positive lexical-only launcher test. No equal-accuracy claim is made for every paraphrase with embeddings disabled. |
| 10. Hidden configuration | Runtime factory captures typed Oracle query settings once and passes them explicitly on resource adoption. Discovery/query credentials stay separate. Explicit protected environment-file selection reaches the child processes. Offline office preflight verifies the effective root/settings before storage/company operations. | `bootstrap/runtime.py`, `bootstrap/office_checks.py`, office/metadata CLI; settings-capture, environment, effective-root and preflight tests. Environment remains a documented process-start input. |
| 11. Chat responsibilities | Extract deterministic routing and Decimal result formatting. Supply one pinned Catalog and an independent SQLValidator explicitly. Remove unused CatalogProvider and executor-to-validator discovery. Keep execution sequencing together rather than creating a class for each step. | `application/routing.py`, `application/results.py`, ports, bootstrap and adapted callers/tests. Entity resolution remains a bounded orchestration step using the query port. |
| 12. HTTP coupling | Replace embedding-to-planning-adapter construction with shared small endpoint/client policy helpers. Preserve private-host, TLS, redirect and proxy restrictions. | `infrastructure/http_policy.py`, inference/embedding adapters; provider-contract tests. |
| 13. Error / endpoint ownership | Domain failures use categories, transport maps HTTP codes. SQLite adapters translate driver errors; transport no longer knows SQLite exceptions. Both chat endpoints share invocation, admission and pipeline completion/failure logs. | `api/compatibility.py`, `api/app.py`, `infrastructure/storage.py`, store/session adapters; API, failure, security and writer-deadline tests. |
| 14. Local extension startup | Stock office composition explicitly supports `disabled` / `private_http` embeddings. Direct Python local providers remain an approved custom-composition seam requiring registration in **each** process; a weights path cannot activate one. | Launcher checks and configuration/operations guides. No runtime, automatic plugin loading or weight download was added for an unselected model. A loopback private HTTP endpoint may be entirely local. |
| 15. Redundant prompt schema | Default structured mode sends the decision schema through `response_format` once; non-schema modes include the schema in context. Keep full-body runtime token counting and output reserve. Preserve direct QueryPlan reply compatibility. | `application/context.py`, HTTP model adapter; model/token-budget contract tests. Real tokenizer/model comparison remains part of office qualification. |
| 16. Boundaries / retention / platform | Architecture test resolves relative imports and has a deliberate violating-import regression. New planning contracts have their own module. Document stopped-worker orphan-projection maintenance and SQLite-aware backup/recovery. Add a macOS full-check CI job. | `tests/tooling/test_architecture.py`, `test_storage_upgrades.py`, `.github/workflows/backend.yml`, operations guide. No unsafe cross-process automatic projection deletion or broad domain rewrite. macOS CI is defined, not executed in this local Windows run. |

## Automatic setup and query behavior

1. An operator supplies protected configuration, approved Oracle accounts, server-owned
   identity/grants and the chosen model/token-counter integration.
2. The office launcher discovers physical Oracle structure and stages evidence. Discovery
   does not invent formulas, certify joins or grant access. Missing certification stops API launch.
3. Matching approved semantic metadata, grants and signed review permit preparation and
   publication of a compatible bundle. Ladybug graph and FTS5 indexes are derived automatically.
   With an approved encoder enabled, metadata vectors and Ladybug vector projections are also
   prepared automatically. There is no manual graph-building step.
4. The launcher supervises one API worker and a separate polling metadata monitor. Changes
   are staged; unsafe mappings can be quarantined. Changed certification still requires review.
   Business-row changes are queried from Oracle; this is schema monitoring, not row CDC.
5. Each question passes current authorization and owned-session checks, bounded admission,
   template/follow-up routing or authorized retrieval and typed SLM planning, PlanValidator
   and graph checks, optional entity resolution, SQLGlot compilation, independent SQL
   validation/capability issuance, read-only bounded execution, exact Decimal formatting,
   response authorization and durable owned history.

There is no general small/medium/large cost classifier, arbitrary SQL fallback, unbounded
queue or large-query job engine. Query shape/output/time budgets and certified semantics
define supported work. Oracle scanned work also needs approved database resource controls.

## Retained stores and operational profile

- **SQLite:** durable metadata, grants/publication authority and owned sessions; FTS5/BM25
  search indexes are derived in memory.
- **LadybugDB:** derived graph and, when enabled, exact-cosine metadata-vector projections.
  No FAISS adapter or additional graph/vector service was introduced.
- **Oracle:** approved office business database and dictionary discovery, with separate accounts.
- **Redis:** optional shared admission for multiworker VM operation; no authority, result
  cache or durable history. The initial single-worker office profile uses in-process admission.
- **Embedding cache:** bounded RAM when enabled; metadata-only bounded restart checkpoints
  are optional and disabled by the office example.

Twenty users may share fewer active inference slots. The office example starts with **one**
active chat and one worker until the selected hardware/model is measured. The HTTP workload
test uses two active slots to verify admission/overload, not to assert 20 parallel generations.
Resource limits multiply across workers, retired leases and overlapping bundles; measure the
whole process set on the target machine before raising them.

## Office prerequisites that source code cannot qualify here

The local Python interpreter links **SQLite 3.50.4**. Restricted office startup now rejects
that native library. Use an approved Python 3.13 build linked to SQLite **3.51.3+**, or the
documented patched 3.50.7 / 3.44.6 branches, and create a fresh target virtual environment.
Updating pip packages or copying this Windows `.venv` does not patch native SQLite. See the
[official SQLite WAL-reset advisory](https://sqlite.org/wal.html#walresetbug).

Office preflight rejects relative, source-tree and recognized synchronized-folder storage.
It cannot certify corporate ACLs, encryption, all network mounts or company approval.
Use protected local paths on the target, not this OneDrive development directory.

The selected SLM/runtime/context window, accurate whole-request token counter, approved
encoder (if enabled), actual Oracle version/schema/DBA context procedures, corporate identity,
real financial answers and target Mac/VM memory/latency still require office qualification.
Approval flags in the example remain false; endpoints, model IDs and paths are examples.
Do not enable an untested corporate integration by treating these examples as approval.

The preserved UI assets are unchanged. Browser/backend integration, a company deployment,
model installation and security penetration testing were not performed in this task.

## Local verification and handover

The mandatory `python scripts/check.py` run completed successfully on the local Windows
Python 3.13 environment:

| Check | Result |
|---|---|
| Ruff correctness / import checks | Passed |
| Ruff formatting | Passed; 177 Python files |
| Pylint | 10.00 / 10 |
| Strict Pyright | Zero errors, warnings or information diagnostics |
| Pytest, including security, compiler goldens and API contracts | **456 passed, 8 skipped, 1 warning** in 350.11 seconds |
| Combined statement / branch coverage | **90%** |
| Pre-commit correctness, formatting and strict typing | All three passed |

The eight skipped tests require an explicitly configured isolated Redis service. No live
Redis qualification was performed in this run. The warning is the existing Starlette
test-client dependency deprecation. Native Ladybug and SQLite tests used synthetic data.
The raw local log is `.local/architecture-fixes-release-check-20261024.txt`.

The updated `dist/nl2sql-office-source-2026-10-24.zip` contains the current public source,
sanitized configuration, tests and documentation with a SHA256 manifest, startup instructions
and verification summary. Packaging checks CRC, every manifest digest and equality with the
current included source files. No populated secrets, runtime databases, model weights or
Windows virtual environment are included. The previous 23 October ZIP predates these fixes.

No runtime dependency was added. No production approval or capacity claim follows from the
synthetic tests. With the fixes, the source is prepared for controlled office integration;
production approval still depends on the explicit external checks above.
