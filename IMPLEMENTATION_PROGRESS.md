# V4.3 development hardening — verified local build (2026-10-16)

## One-command environment setup follow-up

`python setup_env.py` prepares `.venv`, installs the pinned core dependencies and project,
and creates `.env` from the sectioned `.env.example` while preserving existing settings.
Four focused setup regressions passed. A real isolated installation in a path with spaces
passed dependency validation, backend import and explicit `.env` loading. The full follow-up
`scripts/check.py` run passed: 328 tests, 89% coverage and every quality gate.

The full 323-case quality run was followed by one additional focused provider-comparison regression
(passed); application code remained unchanged. Both scripted providers passed all 46 scenarios.

**scripts/check.py exited 0: 323 tests passed, 89% branch-inclusive coverage; Ruff/format, Pylint 10.00/10, strict Pyright and every pre-commit hook passed**. Pytest duration: 316.89s. See reports/DEVELOPMENT_HARDENING_REPORT.md
and reports/quality-hardening.txt. The historical results below describe earlier versions.

The local hardening brief is implemented: configuration/provider factories, normal embedding wiring,
typed schema records/context, bounded vector/cache/build work, reviewed logical joins, startup and
failure isolation, audit regressions, controlled follow-ups, observability and portability evidence.
The clean core-only installation served real loopback HTTP and returned the expected synthetic rows.

All 258 untraced application-load requests were correct at 1/10/25/50 simultaneous callers;
50-caller p95 was 1469.59ms. Memory profiling is a separate traced run.
No enterprise capacity, real model/encoder/native FAISS, corporate identity or company Oracle
qualification is claimed. No frontend work, external publication, deployment or remote push occurred.

# Historical V4.3 status

Final verification (2026-10-16): `python scripts/check.py` exited 0. **249 tests passed, 89% branch-inclusive coverage; Ruff lint/format, Pylint 10.00/10, strict Pyright and all pre-commit hooks passed.** `pip check` passed; pinned dependency audit found no known vulnerabilities. The PowerShell runbook and actual loopback HTTP returned expected rows. Full evidence: reports/quality-check-v43.txt, reports/api-smoke-v43.json and reports/schema-evolution.json.

Local V4.3 discovery, governance, drift/impact, pinned bundles, scheduler and rollback are implemented. Final results are recorded in reports/quality-check-v43.txt. Actual synthetic CLI and loopback HTTP returned the independently expected rows. No corporate Oracle/model/native FAISS qualification or deployment is claimed.

The V4.3 lifecycle is implemented. See SCHEMA_IMPLEMENTATION_REPORT.md, SCHEMA_EVOLUTION_TEST_RESULTS.md and ORACLE_BOOTSTRAP_RUNBOOK.md. The V4.2 record below is historical; its former missing metadata workflow has been added.

# V4.2 implementation matrix - 2026-10-16

Local synthetic backend implementation is verified. The enterprise system is **not production-ready**.
This matrix follows every numbered V4.2 owning document. Complete means the stated local scope only;
partial means implemented code with specified missing behavior or qualification.

| Module | Status | Implemented evidence / remaining scope |
|---|---|---|
| 00 Master register | Complete | Original design pack restored from the pre-existing Git index; original asset manifest preserved |
| 01 Scope / NFR | Partial | Synthetic scope and bounded resources enforced; enterprise SLO acceptance remains open |
| 02 Journeys / intents | Partial | Exact reports, flexible typed planning, clarification, denied/unsupported, follow-ups; broader business intents need certification |
| 03 Architecture / runtime | Complete | Immutable Pydantic contracts, use case, typed adapters, FastAPI lifecycle and snapshot pinning for local runtime |
| 04 Semantic catalog / governance | Partial | Digest-pinned catalog, validated mappings/dependencies/views, failed-load rollback; administrative approval/signature workflow absent |
| 05 Metadata ingestion | Partial | JSON import and SQLite schema reconciliation; enterprise metadata ingestion not connected |
| 06 Retrieval | Partial | Scope-partitioned exact/BM25, optional local vector fusion; no approved encoder performance qualification |
| 07 Join graph / grain / time | Partial | Certified composite keys, ambiguous/missing/fanout refusal, current-only historical refusal, multi-fact preaggregation within declared catalog; general SCD2 effective-interval joins absent |
| 08 Entity / value resolution | Complete | Authorized exact IDs/names/aliases, ambiguity and hidden entity refusal, typed bound filters |
| 09 Routing / confidence | Partial | Templates, grounded typed model, follow-up and safe rejection; no calibrated confidence model or raw-SQL fallback |
| 10 QueryPlan DSL | Partial | Frozen strict DSL including date ranges, fiscal periods, catalog metric formulas, certified combination and aggregate ranking; broader arbitrary expressions remain unsupported |
| 11 SLM / model runtime | Blocked | Private HTTP adapter, identity/role/tool/JSON/retry/token/deadline tests pass; real Gemma endpoint/checkpoint unavailable |
| 12 Deterministic compiler | Partial | Both dialects for declared operators; exact money/null results, binds, grouping/HAVING, safe CTEs and ranking; unsupported operators listed in final report |
| 13 Complex fallback / repair | Partial | Complex supported plans compile deterministically; unrestricted SQL fallback and automatic SQL repair disabled |
| 14 SQL validation / policy | Complete | Independent leaf and complete wrapper checks, signed short-lived capabilities, per-turn grant enforcement, tampering tests |
| 15 Oracle resources | Partial | Injected pool tests cover native binds, numbers, dates, deadlines, cancellation, limits and cleanup; real grants/VPD/preflight unverified |
| 16 API / auth / errors | Partial | EWS and typed API contracts, safe compatible errors, random local tokens/JWT, ownership and request budgets; corporate SSO separate |
| 17 Frontend / accessibility | Not implemented | Existing frontend preserved by instruction; no browser integration or UI edits |
| 18 Sessions / follow-ups | Partial | Durable owned history, optimistic concurrency, per-turn reauthorization, changed-grant redaction; distributed jobs/idempotency/purge absent |
| 19 Provenance / freshness | Partial | Catalog/view/date/range/route provenance, truncation and explicit unknown freshness; source refresh feed unavailable |
| 20 Caching / budgets | Partial | Singleton indexes/graph/pools, hard row/byte/time limits; no shared cache or production capacity qualification |
| 21 Security / privacy | Partial | Adversarial local tests, dependency and targeted secret scan; independent enterprise penetration/SSO/egress review outstanding |
| 22 Deployment / Fulcrum | Blocked | Native startup and runbook only; no approved infrastructure or deployment authorization |
| 23 Observability / SRE | Partial | Correlation IDs, safe logs and stage timings; enterprise telemetry/alerts/dashboards/SLOs unqualified |
| 24 Evaluation | Partial | 46 distinct independent workflow goldens, actual result/coverage/rejection/retrieval/join/plan/latency/memory metrics; real models and domain-held-out 150+ release corpus outstanding |
| 25 Roadmap / gates | Partial | Feasible local stages executed and evidence recorded; external release gates open |
| 26 Approval / RACI | Blocked | Company owners, security, data residency and infrastructure approvals not supplied |
| 27 Contracts / E2E | Complete | Typed contracts plus template/mock to real synthetic SQLite results and real loopback HTTP verification |
| 28 Repository / technology | Complete | Modular package, pinned existing dependencies, no new model/vector/database service |
| 29 Evidence register | Complete | Current reports, commands, test outcomes and limitations recorded locally |
| 30 Quality / CI | Partial | Local Ruff/Pylint/Pyright/Pytest/pre-commit run; hosted CI not run, no code pushed |
| 31 Governed views | Partial | Four synthetic views: dated loans, current accounts, payment events and certified customer portfolio; unsupported grains fail closed; enterprise coverage/certification outstanding |
| 32 Retrieval experiments | Partial | Identical paired business-result comparison harness; toy encoder tests plumbing/regression detection only, real hybrid run blocked |
| 33 Early Oracle compatibility | Partial | Oracle SQL parsing/independent validation and driver-contract tests; no real Oracle execution or cost qualification |
| 34 Traceability / review | Partial | Installed Ponytail audit/review applied and closure evidence saved; enterprise final signoffs outstanding |
| 35 Existing UI contract | Complete | Backend-only EWS contracts tested including errors, auth, user switching/history/tables/empty/clarification; original assets unchanged |

See TEST_RESULTS.md, IMPLEMENTATION_DECISIONS.md, OPEN_BLOCKERS.md and reports/AUDIT_IMPLEMENTATION_REPORT.md.
The original v1 demo and catalog remain unchanged. A separate v2 demo lives in ignored `.local/audit-v2/`.
Run it with `.venv/Scripts/python -m nl2sql serve --settings .local/audit-v2/settings.json`.
The root text exporter remains available and includes the restored original documentation and new backend.
