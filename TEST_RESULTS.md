# V4.3 development hardening — verified local build (2026-10-16)

## Latest environment setup follow-up

`scripts/check.py` exited 0: **328 tests passed in 300.30s, 89% coverage**, Ruff lint and
format, Pylint 10.00/10, strict Pyright and all three pre-commit checks passed. The single
upstream deprecation warning remains. Local raw evidence: `.local/setup-env-quality.txt`.
Four new setup cases cover paths with spaces/different working directories, repeat setup,
preservation of existing `.env` settings, installation failure and unsupported Python.
A real fresh installation also passed `pip check`, backend import and explicit `.env` loading.
Windows newline normalization is accepted when comparing template content.
The results below describe the earlier hardening baseline.

Additional focused verification after the full run: provider comparison regression 1/1 passed in
24.36s; two independent scripted providers each passed 46/46 scenarios. No application code changed.

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

- Full suite: **323 passed**, one upstream warning, **316.89s**; **89%** branch-inclusive coverage.
- All six quality gates passed; no thresholds, tests or assertions were weakened.
- 74 added parametrized regression cases supplement the original 249-test baseline.
- Scripted business workflows: **46/46** scenarios; **37/37** independent numerical results and **9/9** safe outcomes.
- Workflow timings under tracing: p50 **364.22ms**, p95 **699.40ms**; these are not real-model inference times.
- Schema evolution: **30/30** expected results; unchanged/row-only changes do not rebuild; unapproved columns gain no permissions.
- Real clean-install loopback HTTP: health/readiness/chat/components and owned session list/load/delete passed.
- Both original and clean core-only environments passed pip check. No Oracle driver is installed in the clean environment.
- Concurrent BM25 correctness passed at 1/10/25/50 workers; actual application-load measurements are reported above.
- Evidence: reports/quality-hardening.txt, benchmark.json, retrieval.json, schema-evolution.json, concurrency.json,
  api-smoke-hardening.json, portability-hardening.json and preservation-hardening.json.

# Historical V4.3 status

Final verification (2026-10-16): `python scripts/check.py` exited 0. **249 tests passed, 89% branch-inclusive coverage; Ruff lint/format, Pylint 10.00/10, strict Pyright and all pre-commit hooks passed.** `pip check` passed; pinned dependency audit found no known vulnerabilities. The PowerShell runbook and actual loopback HTTP returned expected rows. Full evidence: reports/quality-check-v43.txt, reports/api-smoke-v43.json and reports/schema-evolution.json.

Local V4.3 discovery, governance, drift/impact, pinned bundles, scheduler and rollback are implemented. Final results are recorded in reports/quality-check-v43.txt. Actual synthetic CLI and loopback HTTP returned the independently expected rows. No corporate Oracle/model/native FAISS qualification or deployment is claimed.

The V4.3 lifecycle is implemented. See SCHEMA_IMPLEMENTATION_REPORT.md, SCHEMA_EVOLUTION_TEST_RESULTS.md and ORACLE_BOOTSTRAP_RUNBOOK.md. The V4.2 record below is historical; its former missing metadata workflow has been added.

# Verified results - 2026-10-16

Environment: Windows, Python 3.13.16, existing pinned requirements.lock. No production data or endpoints.

## Baseline and fixes

Reproduced audit baseline: 122 passed, 1 failed (missing original documentation/manifest).
Restored the original directory from the pre-existing Git index without changing its asset hashes.
The restored baseline then passed scripts/check.py: 123 tests and all six quality gates.
Original evidence logs remain in ignored .local/audit-baseline.txt and audit-restored-baseline.txt.

## Current verification

- Ruff lint/format pass; Pylint 10.00/10; strict Pyright zero errors/warnings.
- Full Pytest: **194 passed**, one dependency warning, **90% combined statement/branch coverage**.
- Focused SQL/retrieval/Oracle fixes: 53 passed before the final three security/cancellation cases.
- Final `scripts/check.py`: **exit 0**, all six gates passed, 194 tests, 90% coverage.
  An earlier pre-commit attempt detected my concurrent tracked log/document writes. The final run
  used ignored .local/ output and a frozen worktree; no check was skipped or suppressed.
- pip check: exit 0, no broken requirements.
- pip-audit against all 54 pinned packages: exit 0, no known vulnerabilities, reports/dependency-audit.json.
  Scan tooling is isolated under .local/audit-tools, not a runtime dependency. Advisory results are
  point-in-time public vulnerability data, not penetration or license/SBOM approval.
- Targeted scan: all tracked/nonignored project files checked, no actual local credential/private-key matches; runtime
  directories untracked, UI source diff unchanged, original manifest SHA256 matches. See security-review.json.
- Actual v2 CLI initialization and real loopback HTTP smoke: health, compatible auth error, exact chat
  rows, owned history, cross-user denial and 204 deletion passed. Server stopped. See api-smoke.json.
- Both original packaged UI and current frontend reference are preserved. No browser integration.

One Starlette TestClient deprecation warning recommends httpx2. It is recorded, not suppressed or
resolved by adding an unapproved second HTTP library. No ResourceWarnings remain.

## Workflow evaluation

scripts/benchmark.py exit 0: **46 distinct questions, 46 passing cases**. Independently expected
business results: 37/37 eligible answers; coverage 37/37; nine expected safe non-answer outcomes,
all without business execution. Retrieval recall, join correctness, typed-plan validity and SQL
execution correctness are 100% for this local corpus. Scripted plans are NOT Gemma language accuracy.

The saved run measured p50 197.3001 ms, p95 393.8366 ms, DB p50 9.7646 ms, 36 mock model calls,
3,128,754 Python-traced peak bytes. Token counts remain null. These are local single-run workflow
measurements with allocation tracing and concurrent tooling; no production latency claim is made.
reports/benchmark.json includes every question/outcome, metric denominators and limitations.

scripts/retrieval_benchmark.py exit 0 records lexical results and hybrid not_run_no_approved_encoder.
A toy encoder test runs identical paired workflows and deliberately detects an out-of-domain
regression (45/46 hybrid outcomes versus 46/46 lexical); it tests the harness, not semantic quality.
No encoder/FAISS/model was installed or downloaded. Domain-owned 150+ held-out cases and A-G/real-model
comparisons remain release gates.

## Coverage scope and external boundaries

Tests cover EWS contracts/errors/auth/ownership/history/user switching/empty/clarification, provider
identity/JSON/tools/roles/retries/deadlines/tokens, injection and raw-SQL refusal, graph/composite/fanout,
financial/null/fiscal/date/ranking/multi-fact goldens, policy/bind/wrapper tampering, signatures/expiry,
catalog activation, scoped retrieval and concurrency/session isolation. Oracle injected-driver tests
cover native dates, exact decimals, timestamp serialization, read-only setup, row/byte/schema budgets,
watchdog timeout/cancel, context cleanup/drop/release and pool approval guards.

Real Gemma: NOT RUN. Real Oracle: NOT RUN. Real embedding comparison: NOT RUN. Hooks: execution
UNVERIFIED despite installed/enabled plugin and trust records. Hosted CI, production load/SSO/VPD,
penetration/egress/license/SBOM, deployment and browser integration: NOT RUN.

## Final command outcomes

All commands below were executed in the pinned environment. The combined runner invokes the first
six checks with `python -m`; no hosted CI result is inferred.

| Command | Exit | Result |
|---|---|---|
| python -m ruff check . | 0 | Pass |
| python -m ruff format --check . | 0 | Pass |
| python -m pylint backend/nl2sql | 0 | 10.00/10 |
| python -m pyright | 0 | Strict, zero errors/warnings |
| python -m pytest -q | 0 | 194 passed, 1 dependency warning; 90% statement/branch coverage |
| python -m pre_commit run --all-files | 0 | All three configured hooks pass |
| python scripts/check.py | 0 | All six gates completed |
| python scripts/benchmark.py | 0 | 46 distinct known-answer workflows pass |
| python scripts/retrieval_benchmark.py | 0 | Lexical measured; hybrid explicitly not run |
| python -m pip check | 0 | No broken requirements |
| pip-audit -r requirements.lock --no-deps --disable-pip --format json | 0 | 54 packages; no known advisories |

Final combined log: reports/quality-check.txt. Final Pytest duration: 88.38 seconds.
Focused final checks also passed: 46 security cases, 25 provider cases and 17 catalog cases.
