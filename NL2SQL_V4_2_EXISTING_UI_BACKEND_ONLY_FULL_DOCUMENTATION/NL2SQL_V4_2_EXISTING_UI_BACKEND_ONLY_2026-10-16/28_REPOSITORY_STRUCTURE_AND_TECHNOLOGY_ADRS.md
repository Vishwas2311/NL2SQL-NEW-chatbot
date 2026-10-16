# 28 — Repo Layout, Dependency Choices, Configuration and ADRs

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Draft for review; no implementation or company production validation performed.  
**Document owner:** Tech lead + platform  
**Gate:** P0  
**Baseline reference:** V4 research/blueprint supplied on 2026-10-15.  
**Data policy:** Fictional examples only; actual company schema and customer data stay in approved office systems.

> **Core distinction:** this document specifies future behavior. It does not claim that these modules, controls, model benchmarks, or Oracle permissions are already deployed.

## Design specification

## Codebase shape
One backend-first repo with `ui_reference/` immutable supplied HTML/CSS/JS snapshots (optional documentation assets; not a UI source project), `backend/app/` modular FastAPI, `metadata/synthetic/`, `metadata/catalog/`, `evaluation/`, `deployment/`, `docs/`. Backend modules: `api`, `auth`, `sessions`, `catalog`, `retrieval`, `value_resolver`, `graph`, `planning`, `llm`, `compiler`, `sql_validation`, `database`, `results`, `telemetry`, `orchestration`. Keep import direction inward (domain contracts independent of adapters). Admin catalog publishing lives outside normal query path.

## Technology defaults and alternatives
| Layer | Initial choice | Change when |
|---|---|---|
| API | FastAPI + Pydantic | Only if platform mandates framework |
| UI | Supplied EWS HTML/CSS/JS; no new frontend build | Only an explicitly approved owner request allows UI modification |
| Synthetic DB | SQLite | Oracle-specific tests, in company Oracle test DB |
| Catalog | Signed/versioned JSON + optional SQLite index | Requires approvals/workflow at larger scale |
| Lexical | Exact/BM25 | Relevance measurements require replacement |
| Graph | Custom adjacency/NetworkX | Verified graph size/query requirements justify service |
| Embeddings | Optional approved local model/FAISS | Measured recall and operations justify server |
| SLM | Gemma 4 12B via provider | Controlled benchmark proves alternative better |
| SQL AST | SQLGlot + custom checks | Oracle dialect tests require another tool |
| Oracle | python-oracledb | Organization requires supported alternative |
| Tests | pytest + EWS API contract E2E + golden runner; later browser smoke tests | Standardize under corporate CI |

## Architecture decision records
ADR-001 compiler-first with fallback; ADR-002 no mandatory graph DB; ADR-003 adaptive lexical/vector; ADR-004 metadata and policy snapshot versions; ADR-005 model-provider abstraction; ADR-006 private self-hosted inference; ADR-007 value resolver isolated from schema retrieval; ADR-008 validator capability gate; ADR-009 mandatory compatibility adapter for sole existing EWS UI (no React); ADR-010 Oracle read-only identity/independent session-write identity. Each ADR has context, options, tradeoffs, measurable decision trigger and rollback conditions.

## Configuration classes
Non-secret app flags, published catalog digest, provider/endpoint aliases, time/token/query budgets, index mode, DB pool size and timeouts, auth issuer/audience, error/telemetry settings. Secret references come from approved secret management; never source-control credentials, real Oracle DSNs or API keys. All environment configuration has schema validation and safe defaults.

## Tool policy
No extra agent frameworks solely for marketing. No Docker requirement. Before adding another database, prove measurable improvements versus lexical+in-memory graph. No auto-run arbitrary user SQL via MCP or shell access. Dependency licenses, model weights and security advisories receive company review.



## V4.1 proposed initial technology decisions (supersede ambiguous alternatives above)
| Category | **Proposed default** | Not required by default | Reconsider on evidence |
|---|---|---|---|
| Lexical search | SQLite FTS5 + `bm25()` index over *metadata*; exact alias dictionary | Elasticsearch, OpenSearch | Corporate platform standard or measured query scale |
| Vector search | **Feature-flag OFF**; interface present, local approved encoder + FAISS if promoted | Qdrant/Milvus/vector server | Held-out retrieval/answer gain within measured latency + security budget |
| Physical join graph | **NetworkX in-process**, rebuilt from certified relationships | Neo4j, Graphify runtime | Measured traversal/scale or enterprise service requirements |
| Governed semantic views | **Catalog-side logical views** first; physical Oracle views only under DBA approval | Any automatic Oracle DDL | Performance/security/query-plan evidence |
| SLM | Gemma 4 12B baseline behind provider adapter | Multiple agents, fine-tuning | Same test suite shows another model is better |
| SQL | Typed plan DSL → deterministic compiler; guarded operator fallback OFF initially | Arbitrary raw model SQL | Approved per-domain tests and release gate |
| Deployment | Modular FastAPI app; private SLM server as resource demands | Mandatory Docker or extra DB servers | Company environment and concurrency evidence |
| Quality | Ruff + Pylint complementary checks, strict Pyright, pytest, backend API contract CI | Duplicate unmanaged linters | Approved corporate standards |
These are **engineering proposals, not approvals, implemented features, or measurements**. Record ADR-011…ADR-018 in [26](./26_DOCUMENT_APPROVAL_RACI_AND_OPEN_DECISIONS.md) and [34](./34_TRACEABILITY_DECISIONS_AND_FINAL_REVIEW.md). See [30](./30_CODING_STANDARDS_CODEX_AND_CI.md), [31](./31_GOVERNED_SEMANTIC_VIEWS_AND_COVERAGE.md), [32](./32_RETRIEVAL_TECH_CHOICES_AND_EXPERIMENTS.md) and [33](./33_ORACLE_EARLY_COMPATIBILITY_AND_PREFLIGHT.md).

---

## Deliverables / artifacts to review

Canonical repo directory tree, tech decision register, config schema, dependency license review and ADR template

## Acceptance tests and exit criteria

Isolated unit tests with mock providers, architecture import boundaries, reproducible install and startup

## Open decisions and evidence required

Company language/tool standard? Existing EWS UI reuse is fixed; allowed package/license policy and later auth/browser integration remain open.

## Related documents

[01](./01_SCOPE_PRD_AND_NFR.md), [03](./03_SYSTEM_ARCHITECTURE_AND_RUNTIME.md), [11](./11_LOCAL_SLM_MODEL_CONTEXT_AND_RUNTIME.md), [14](./14_SQL_VALIDATION_POLICY_AND_SECURITY.md), [15](./15_ORACLE_ADAPTER_PREFLIGHT_AND_RESOURCES.md), [16](./16_API_AUTH_AND_ERROR_CONTRACTS.md), [17](./17_FRONTEND_UX_RESULT_TABLES_AND_ACCESSIBILITY.md), [22](./22_PRIVATE_DEPLOYMENT_INFRA_AND_FULCRUM.md), [25](./25_IMPLEMENTATION_ROADMAP_DEPENDENCIES_AND_GATES.md)


---

## CI quality gates and dependency pinning
A new code change must run style/type checks (mypy or pyright, linting), unit and synthetic integration tests, query/contract schema compatibility and full deny suite for SQL-affecting modules. Track reproducible dependency versions, SBOM and model runtime IDs. Catalog YAML/JSON changes trigger metadata validation, index rebuild consistency checks and affected metric golden tests. Production Oracle tests are gated to a company-approved environment, never run from public CI with broad secrets.

### ADR template
Context/problem; alternatives; decision; reasoning; correctness and performance tradeoffs; security/privacy implications; measurable success condition; rollback threshold; reviewer/approval. An ADR changing an API contract or parser version includes backward-compatibility and migration plan.

---

## Historical V4 Baseline Requirements (reference only; superseded where V4.1 refines them)

> **Historical UI exclusion:** Any older requirement below to create a React/TypeScript/Vite frontend, new browser pages, screens, or UI build/test pipeline is superseded by the user decision. These are historical notes, **not implementation tasks**. Preserve existing capabilities for later integration via document 35.

> This is preserved from the earlier planning draft for comparison. The current V4.1 design section, companion docs 30–34, the approved ADR register, and subsequent validated contracts take precedence on changes explicitly addressed in the V4.1 refinement. Historical descriptions of optional vector providers, open SQL fallback, and late Oracle tests are **not** new mandatory decisions.


The following material records relevant requirements from the previously agreed V4 blueprint. The sections above are the detailed module design and take precedence where they add stricter controls. Original V4 is a **proposed architecture**, not independently verified production source.

# 24. Complete Project Structure

Recommended modular monolith layout:

```text
nl2sql-chatbot/
|
|-- ui_reference/   # frozen pre-built UI references, no frontend build
|   |-- index.html
|   |-- script.js
|   |-- style.css
|
|-- backend/
|   |-- app/
|   |   |-- main.py
|   |   |-- config.py
|   |   |
|   |   |-- api/
|   |   |   |-- chat.py
|   |   |   |-- sessions.py
|   |   |   |-- feedback.py
|   |   |   |-- health.py
|   |   |
|   |   |-- auth/
|   |   |   |-- identity.py
|   |   |   |-- authorization.py
|   |   |   |-- policies.py
|   |   |
|   |   |-- catalog/
|   |   |   |-- models.py
|   |   |   |-- loader.py
|   |   |   |-- validation.py
|   |   |   |-- versioning.py
|   |   |   |-- semantic_registry.py
|   |   |
|   |   |-- retrieval/
|   |   |   |-- exact_search.py
|   |   |   |-- bm25_search.py
|   |   |   |-- vector_adapter.py
|   |   |   |-- candidate_ranker.py
|   |   |   |-- grounding.py
|   |   |
|   |   |-- graph/
|   |   |   |-- relationship_graph.py
|   |   |   |-- join_resolver.py
|   |   |   |-- grain_validator.py
|   |   |
|   |   |-- planning/
|   |   |   |-- intent_router.py
|   |   |   |-- query_plan.py
|   |   |   |-- plan_validator.py
|   |   |   |-- clarification.py
|   |   |
|   |   |-- models/
|   |   |   |-- provider.py
|   |   |   |-- gemma_adapter.py
|   |   |   |-- context_builder.py
|   |   |   |-- structured_output.py
|   |   |
|   |   |-- compiler/
|   |   |   |-- semantic_compiler.py
|   |   |   |-- oracle_dialect.py
|   |   |   |-- expressions.py
|   |   |   |-- templates.py
|   |   |
|   |   |-- sql/
|   |   |   |-- sql_validator.py
|   |   |   |-- security_rules.py
|   |   |   |-- semantic_checks.py
|   |   |   |-- fallback_generator.py
|   |   |
|   |   |-- database/
|   |   |   |-- interface.py
|   |   |   |-- sqlite_adapter.py
|   |   |   |-- oracle_adapter.py
|   |   |
|   |   |-- sessions/
|   |   |   |-- manager.py
|   |   |   |-- repository.py
|   |   |   |-- memory.py
|   |   |
|   |   |-- responses/
|   |   |   |-- formatter.py
|   |   |   |-- charts.py
|   |   |
|   |   |-- telemetry/
|   |   |   |-- logging.py
|   |   |   |-- metrics.py
|   |   |   |-- tracing.py
|   |   |
|   |   |-- orchestration/
|   |   |   |-- query_service.py
|   |   |   |-- execution_router.py
|   |
|   |-- tests/
|   |   |-- unit/
|   |   |-- integration/
|   |   |-- security/
|   |   |-- performance/
|   |
|   |-- pyproject.toml
|
|-- metadata/
|   |-- synthetic/
|   |-- semantic_definitions/
|   |-- relationships/
|   |-- metrics/
|   |-- schemas/
|
|-- evaluation/
|   |-- golden_questions/
|   |-- expected_results/
|   |-- benchmark_runner/
|   |-- reports/
|
|-- deployment/
|   |-- local/
|   |-- office/
|   |-- production/
|
|-- docs/
|   |-- architecture/
|   |-- contracts/
|   |-- runbooks/
|   |-- decisions/
|
|-- README.md
```

This is a proposed code organization, not a requirement to implement every file immediately.

Create only the components needed for each milestone.

Keep the system as a modular monolith initially. Introduce distributed services only when deployment requirements justify them.

---

---

# 28. Decisions We Are Locking

| Architecture question | Final decision |
|---|---|
| Build NL-to-SQL backend from scratch and later attach existing UI? | Yes |
| Backend framework | FastAPI |
| Frontend | Existing HTML/CSS/JavaScript; later integration only |
| Primary database | Oracle |
| Development database | Synthetic SQLite |
| Primary model | Gemma 4 12B baseline |
| Model tightly coupled to backend? | No |
| Semantic catalog required? | Yes |
| Business metric governance? | Yes |
| Verified SQL relationships? | Yes |
| Graphify required? | No |
| Neo4j required? | No |
| Dedicated vector DB required? | No |
| Exact/keyword retrieval? | Yes |
| Embeddings? | Optional, benchmark-driven |
| Structured query plans? | Yes |
| Deterministic SQL compiler? | Yes |
| Complex-query SLM fallback? | Yes, restricted |
| Independent SQL validation? | Mandatory |
| Read-only business query identity? | Mandatory |
| Multiple AI agents? | Not initially |
| Fine-tuning? | Only after baseline evaluation |
| Private inference? | Required |
| Full observability? | Required |
| Business-result evaluation? | Required |

---
