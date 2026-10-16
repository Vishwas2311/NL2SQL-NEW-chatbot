# V4.2 audit remediation report - 2026-10-16

Feasible local backend audit fixes are implemented. Enterprise runtime/release qualification remains
blocked. Every numbered module and status is in [IMPLEMENTATION_PROGRESS.md](../IMPLEMENTATION_PROGRESS.md).
No frontend, corporate data access, model download, source publication or deployment occurred.

## Delivered behavior

1. Reproduced 122 passing tests and the missing preservation-manifest failure. Restored the full
   original documentation package from its existing Git index. Kept the original expected hashes
   and unchanged preservation test. Restored baseline passed all six gates with 123 tests.
2. EWS compatibility errors expose safe detail/message/response/results fields while retaining the
   nested typed error. Authentication, current server grants and session ownership remain enforced.
3. Extended the strict catalog/plan/compiler contracts for date ranges, fiscal periods, snapshot
   reporting grain, net amounts, exact percentages, aggregate CTEs, certified multi-fact reports and
   aggregate ranking. Every source and complete CTE/window wrapper is independently validated.
4. Added exact alias span disambiguation, shared-alias clarification, optional scope-safe local
   vector fusion, safe encoder startup cleanup and identical paired business-result experiments.
5. Private-model replies must report the exact configured identity, assistant role, strict QueryPlan
   and no tools. Existing reused-client, timeout/retry/budget/token controls remain in place.
6. Oracle uses typed DATE binds, exact NUMBER conversion, DATE/TIMESTAMP serialization, output-schema,
   row/byte/time limits, cancellation watchdog and mandatory rollback/context reset. Unsafe cleanup
   drops pooled connections. Tests inject a simulated pool; no Oracle endpoint was contacted.
7. Replaced two repeated benchmark questions with 46 distinct workflow goldens and independent expected
   results. Added explicit safe rejection, coverage, retrieval, joins, plan/execution, latency, model
   calls, database timing and Python allocation metrics. No model accuracy number is invented.
8. Closed review findings on physical numeric/dimension types, historical/current mixed reports,
   derived units/scales/time, shared
   aliases, CTE wrappers, NULL ordering/predicates schema qualifiers and internal model-context dependency IDs. Regression tests run for
   both supported SQL dialects. Read-only execution and signed capabilities remain mandatory.

## Exact changed or added implementation files

Updated `backend/nl2sql/`: `__main__.py`, `api.py`, `catalog.py`, `compiler.py`, `database.py`,
`domain.py`, `middleware.py`, `model.py`, `oracle.py`, `planning.py`, `retrieval.py`, `security.py`,
`service.py`, `synthetic.py`.

Added `backend/nl2sql/`: `compatibility.py`, `composite.py`, `evaluation.py`, `ranking.py`,
`retrieval_experiment.py`, `sql_types.py`, `synthetic_extensions.py`.

Updated `scripts/benchmark.py`; added `scripts/retrieval_benchmark.py` and
`metadata/synthetic/catalog-v2.json`. Updated `tests/test_providers_failures.py` and
`tests/test_security.py`, `tests/test_catalog_sessions.py`; added `tests/test_advanced_sql.py`, `test_ews_errors.py`,
`test_oracle_adapter.py` and `test_retrieval_extensions.py`.

Updated README, IMPLEMENTATION_PROGRESS, IMPLEMENTATION_DECISIONS, TEST_RESULTS, OPEN_BLOCKERS,
`docs/PONYTAIL.md`, `docs/OPERATIONS.md` and the evidence files in reports/. The entire missing
`NL2SQL_V4_2_EXISTING_UI_BACKEND_ONLY_FULL_DOCUMENTATION/` was restored unchanged from the original
index. The earlier standalone `export_project_to_txt.py` and its tests are retained and the text
export is refreshed. No existing UI asset, dependency lock, auth module or preservation test changed.

## Supported SQL and explicit limits

Supported: SUM/COUNT/MIN/MAX, exact displayed AVG, certified composite-key many-to-one joins,
multiple grouping fields, nested typed AND/OR, comparison/IN/null filters, HAVING for supported
measures, bound values, deterministic ordering/limits, as-of snapshots, half-open event ranges,
April fiscal years from catalog, snapshot ranges retaining date grain, certified SUM-SUM and
percentage measures, aggregate CTEs, customer-grain independent fact preaggregation, ROW_NUMBER and
DENSE_RANK after aggregation with explicit tie behavior, SQLite/Oracle rendering and validation.

Unsupported: arbitrary joins/formulas/SQL, recursive/arbitrary CTEs, general analytic/window
expressions, average/ratio ordering/HAVING/ranking, composite HAVING/windows/nonadditive measures,
historical current-only attributes, period-over-period comparisons, FX/currency aggregation and
SCD2 effective-interval joins and business timezone TIMESTAMP query semantics. Unsupported plans fail explicitly before execution.
There is no unrestricted raw SQL fallback or model database tool.

## Actual evaluation

`reports/benchmark.json`: 46/46 distinct local cases; 37/37 eligible expected result sets; nine safe
non-answer outcomes without business execution. Local supported coverage, retrieval recall, joins,
plan validity and SQL execution correctness all passed for this corpus. Mock model calls: 36;
input/output token counts: unavailable. Python traced peak: 3,128,754 bytes. p50 197.3001 ms,
p95 393.8366 ms; DB p50 9.7646 ms. Allocation tracing and concurrent tooling affect these figures.

This is scripted-plan workflow correctness, not Gemma language accuracy, a domain-held-out launch
benchmark, Oracle performance or production SLO evidence. The optional hybrid report truthfully says
not_run_no_approved_encoder. Its toy-encoder test detects a 45/46 versus 46/46 regression; the toy is
not promoted as an embedding model. Domain-owned 150+ held-out cases and A-G/real model comparisons
remain required.

## Model, Oracle, Ponytail and release gates

Gemma: mock and HTTPX transport integration verified; real inference NOT RUN. No approved model
endpoint/checkpoint was supplied and no weights were downloaded. Configure the exact approved
private runtime identity, then run real structured-plan, result, accuracy, token and load checks.

Oracle: dialect/independent AST and injected-driver tests verified; real database tests NOT RUN.
Require an approved synthetic test schema, DBA grants/VPD/context policy, native data mappings,
resource manager/preflight and real pool/cancel/date/precision qualification before application wiring.

Ponytail: official DietrichGebert/ponytail 5.2.0 manifest and enabled plugin setting verified.
Codex configuration has three trust-hash records; this agent did not write them. Actual lifecycle
execution remains unverified without /hooks/runtime evidence. Official coding/audit/review skills
were manually applied; closure evidence is in PONYTAIL_REVIEW.md and PONYTAIL_AUDIT.md.

UI: original HTML/CSS/JavaScript match their supplied SHA256 manifest; current frontend reference
has no working-tree diff. No UI edits or browser integration. Local credentials remain outside source
and exports. No company database, push, hosted CI, deployment or hooks trust bypass was performed.

See TEST_RESULTS.md for exact commands, exit codes, counts, coverage and remaining warning;
OPEN_BLOCKERS.md for the complete external integration and approval checklist.

## Final quality result

`python scripts/check.py` exited 0: Ruff lint/format, Pylint 10/10, strict Pyright, **194 tests**,
**90% combined statement/branch coverage**, and all pre-commit hooks pass. One Starlette TestClient
deprecation warning remains recorded. pip check and pip-audit exited 0; 54 pinned packages have no
known advisories in the saved scan. These checks do not replace enterprise security approval.

Updated evidence files: `reports/api-smoke.json`, `benchmark.json`, `retrieval.json`,
`dependency-audit.json`, `security-review.json`, `quality-check.txt`, `PONYTAIL_AUDIT.md`,
`PONYTAIL_REVIEW.md` and this `AUDIT_IMPLEMENTATION_REPORT.md`.
