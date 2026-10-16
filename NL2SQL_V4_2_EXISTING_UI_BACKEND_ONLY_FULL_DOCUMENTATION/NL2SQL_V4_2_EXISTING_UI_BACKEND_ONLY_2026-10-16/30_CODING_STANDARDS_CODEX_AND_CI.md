# 30 — Professional Coding Standards, Codex Workflow and CI Quality Gates

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Proposed for team review. **Owner:** Tech lead + security + QA. **Scope:** All code written for V4.1. No existing repository or CI run is claimed.

## Goal and mandatory boundaries
Build a maintainable, testable, privately deployable *modular monolith*. The first coding task is a small synthetic vertical slice, not an auto-generated set of empty microservices. Domain models and semantic contracts must not import FastAPI, Oracle, model runtime, or UI packages. Providers depend on domain interfaces, not vice versa.

| Concern | Default | Enforcement |
|---|---|---|
| Backend | Supported pinned Python, FastAPI, Pydantic v2 | App factory, typed request/response, lifecycle cleanup |
| Formatting | Ruff formatter | `ruff format --check backend` |
| Lint | Ruff with vetted correctness/style rules | `ruff check backend` |
| Complementary lint | Pylint nonduplicative rules | `pylint backend/app` with agreed config |
| Type checks | Pyright strict for app domain/interfaces | `pyright` pinned version; targeted documented exceptions |
| Backend tests | Pytest + pytest-cov | Golden semantic/SQL and negative security tests |
| Existing UI (later integration) | Immutable uploaded HTML/CSS/JavaScript assets; no new frontend code | No frontend build gate now; later approved JS lint/static security and browser checks on integration changes |
| E2E | Pytest/httpx EWS API wire-contract tests now | Playwright browser smoke tests only during later approved UI integration |
| Hooks | Pre-commit | Fast local lint/format/secret checks |
| CI | Approved provider (GitHub Actions only if allowed) | Install locked deps; run all gates; upload synthetic test reports |
| Security | Secret scan, dependency/license/SBOM scan | Break build for leaked secrets and disallowed packages |
| Docs | ADRs, typed-contract changelog, developer runbook | PR template requires reference and impact review |

## Quality rules

**Agent lifecycle policy (Ponytail):** During Codex implementation, evaluate the already-authorized official Ponytail plugin and lifecycle hooks. If approved and activated, use it consistently across backend modules as agent guidance for simple maintainable code; its activation must be independently confirmed. Ponytail is separate from Pylint, Ruff, strict Pyright, Pytest and Git pre-commit. Never replace CI/security gates with agent hooks, install unreviewed third-party code or claim activation when unavailable. The existing UI reference files are never rewritten by this hook workflow. See `CODEX_BACKEND_ONLY_HANDOFF.md`.

- All public Python APIs have types; avoid `Any` outside strict adapter boundaries. Use dataclasses for immutable internal value objects and Pydantic at request/external trust boundaries. Keep exceptions typed and error codes stable.
- Separate `domain`, `application`, `ports`, `adapters`, `api`. Routes orchestrate only, no SQL generation/business calculations in handlers. Keep model and DB protocols swappable and mocked.
- Never trust model-provided SQL, table identifiers, authorization, schema changes, unsafe JSON or direct shell commands. Every SQL route goes through validated capabilities and read-only DB permissions.
- Prefer focused functions with clear names; document nonobvious invariants and business formulas. Use `ruff` and `pylint` complementarily; do not auto-disable failing rules. `pyright` strict may require allowlisted stubs for external dependencies, documented with owner.
- Use explicit timezone-aware UTC timestamps internally and record business reporting time separately. Decimal for monetary figures; never silently cast precise Oracle NUMERIC to float. All DB values use binds.
- Use structured logging with request ID but no sensitive literals/customer rows. Secrets via approved manager, not `.env` committed. Do not install packages or send data to third-party endpoints without permission.
- Every behavior change has relevant tests, docs and an ADR update if it changes architecture; no claims of accuracy, model support or test passing without execution evidence.

## Testing policy
**Test pyramid:** domain unit tests (compiler, grain, joins, policy) → provider contract tests (mock SLM/DB) → synthetic E2E → gated approved Oracle dialect tests → independent authorized enterprise goldens. Property/fuzz tests for SQL parse/deny behavior and typed filters; regression corpus for source mapping, view grain and time rules. Track meaningful coverage and branch coverage in core modules; target/threshold to be approved, not invented.

**Minimum PR gate:** format, lint, strict types, unit tests, synthetic SQL/result goldens, deny suite for SQL changes, API/JSON schema compatibility, legacy EWS API contract checks when backend behavior changes, secret/dependency scan, and changelog on behavior modifications. Failed or skipped gates must be shown as failures/blockers, not silently reported as passes.

## AGENTS.md reference template (write into code repository at Codex scaffold time)
```md
# AGENTS.md — V4.2 Backend-Only Enterprise NL2SQL
Read docs/00_MASTER_DOCUMENT_REGISTER_AND_PRECODING_CHECKLIST.md and the owning module design before coding.
Use synthetic data only until enterprise authorization is verified. Never copy customer rows, private schema DDL or credentials into external tools.
Follow typed domain ports, strict authentication, approved catalog/version bindings, compiler-first SQL and independent validation. No model-initiated DB execution. No unreviewed semantic metric/relationship changes.
Default search: exact + SQLite FTS5/BM25; optional local embeddings/FAISS OFF until benchmark promotion. Graph: in-memory NetworkX of verified edges. No Neo4j, Qdrant or Milvus server by default.
SLM: provider-adapted Gemma baseline, compact typed plan. Guarded fallback OFF by default until class-level approval.
Do not build any replacement UI or React/TS/Vite scaffold; preserve `ui_reference/` for approved later integration. Implement mandatory `/ews-chatbot/*` compatibility adapter with tests in the backend.
For each task: summarize requirements; inspect current files; implement the smallest coherent change; add tests; run format/lint/types/tests/deny suite; report exact commands and results; update docs/ADRs; stop at phase gate for review.
Do not claim tests passed if not run, fabricate Oracle connectivity, generate unrestricted SQL or commit secrets. Ask for owner approval for major architecture changes and external services.
```
The template is not a claim that the file exists in any Codex repo until scaffolding actually creates it.

## Recommended Python `pyproject.toml` configuration outline (illustrative)
```toml
[tool.ruff]
line-length = 100
target-version = "py312"  # adjust to company-approved supported interpreter
[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "I", "B", "UP", "S"]
[tool.pytest.ini_options]
testpaths = ["backend/tests"]
addopts = "-ra --strict-markers"
```
Security-lint exclusions and Python version must be explicitly decided and documented; don't paste this unchanged if corporate standards differ.

## Directory policy
```
backend/app/domain/       # pure types: metric, view, plan, proofs, typed errors
backend/app/application/  # use cases and route control
backend/app/ports/        # model, catalog, search, Oracle and persistence protocols
backend/app/adapters/     # FAISS(optional), SQLite FTS5, NetworkX, MLX/vLLM, Oracle
backend/app/api/          # FastAPI transport only
ui_reference/              # uploaded HTML/CSS/JS assets ONLY; no new UI build or frontend scaffolding
metadata/synthetic/       # fictional fixtures
qa/goldens/               # versioned expected answers and deny tests
docs/adr/                 # immutable decision records
```
No need to create all folders until real code requires them. Keep the root monorepo deployable without Docker.

## Codex task/PR checklist
1. Link relevant spec and acceptance criteria; preserve source-vs-inference distinctions.
2. List changed public contracts, versions, source and security impacts.
3. Implement tests before/with high-risk logic, including failure cases.
4. Record precise CLI commands and their exit status; do not report a `PASS` on unexecuted checks.
5. Document limitations and remaining approval gates; stop before next phase.

## Approval requirements
Company Python baseline/CI provider, dependency licenses, exact lint profiles, minimum test thresholds, hosting and secret-management choices remain **open owner decisions** (see 26, 28 and 34). The professional quality gate is required; a particular tool configuration may change only through recorded ADR.
