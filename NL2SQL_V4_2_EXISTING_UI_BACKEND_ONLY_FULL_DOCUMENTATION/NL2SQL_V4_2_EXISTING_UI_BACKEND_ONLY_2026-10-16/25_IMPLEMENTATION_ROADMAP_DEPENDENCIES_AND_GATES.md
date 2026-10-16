# 25 — Phased Delivery Roadmap, Backlog, Dependencies and Exit Gates

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Draft for review; no implementation or company production validation performed.  
**Document owner:** Tech lead + QA + product  
**Gate:** P0  
**Baseline reference:** V4 research/blueprint supplied on 2026-10-15.  
**Data policy:** Fictional examples only; actual company schema and customer data stay in approved office systems.

> **Core distinction:** this document specifies future behavior. It does not claim that these modules, controls, model benchmarks, or Oracle permissions are already deployed.

## Design specification

## Governance-first sequence
Each phase produces an executable testable deliverable, not only code fragments. Do not begin real Oracle integration before local security and business-correctness tests pass. No team should begin unapproved production writes or copy internal catalog values into portable development.

| Phase | Primary deliverable | Mandatory exit evidence |
|---|---|---|
| 0 | Sign-off on document pack and open decisions | PRD, architecture, catalog/privacy/SLM deployment owners named |
| 1 | FastAPI backend scaffold, mock identity, EWS contract tests | Health, typed backend API, CI and compatibility fixtures; **no UI scaffold** |
| 2 | Synthetic Oracle-like schema + versioned catalog | Publish/rollback and conflict tests pass |
| 3 | Certified metrics, graph joins, grain and temporal rules | Known-answer join/metric fixtures correct |
| 4 | Value resolver + lexical retrieval | Safe aliases, ambiguous value tests; lexical baseline |
| 5 | Typed DSL + plan validator + deterministic templates | Certified templates run with 0 model calls |
| 6 | Gemma adapter + compact context + structured planning | Typed plans and inference timing measured |
| 7 | Semantic Oracle SQL compiler + bounded fallback | SQL golden/compile-correctness tests pass |
| 8 | Independent validator + preflight + query executor | Security suite proves no unsafe DB invocation |
| 9 | Sessions, clarification, provenance and EWS API adapter | Complete synthetic multi-turn **API** E2E works; browser integration later |
| 10 | Benchmark and harden | Accuracy, coverage, p50/p95, concurrency reported |
| 11 | Approved Oracle and company identity integration | DBA/security/domain sign-offs and Oracle golden suite |
| 12 | Production deployment/canary | Runbook, monitoring, kill switch and rollback rehearsal |

## Parallelization
Backend-owned EWS wire-contract mocks and adapter tests can proceed after phase 0/1; do not create mock screens. QA begins synthetic fixtures and goldens at phase 2. ML adapter work can begin with mocked catalog at phase 3, but real end-to-end comparison must use the stable catalog and DSL contracts. Operations provisioning may begin early; it must not block local synthetic implementation.

## Delivery backlog format
Every ticket contains feature ID, owner, inputs/outputs, failure semantics, dependencies, synthetic fixtures, tests, observability, security impact and demo steps. PR reviewers reject changes that bypass catalog/policy validators. Architectural changes require ADR entry and impact assessment.

## Exit and rollback
After each release gate, freeze and version artifacts, run regression and publish evidence. If a new retrieval method or model degrades accuracy/security, revert that component while keeping same API and catalog version. No automatic rollout with missing DBA approval or unresolved security findings.



## V4.1 revised engineering milestones and dependency gates
| Milestone | Requirement | Exit evidence |
|---|---|---|
| 0.5 | Codex/CI/coding standards baseline | Ruff, Pylint, strict Pyright, pytest, contract tests and secret scan; AGENTS.md signed off; no React/TypeScript toolchain |
| 2A | Canonical catalog + logical semantic-view contracts | Versioned view/metric schemas; dual fact/grain and policy tests |
| 3A | Verified view→physical mapping + join proofs | Composite joins, temporal tests, fan-out rejections |
| 4A | Lexical-only FTS5 baseline + optional vector adapter | Reproducible search fixtures; vector OFF by default |
| 5A | One complete synthetic vertical slice | Question→QueryPlan→compiler→validator→synthetic executor→provenance with no confidential data |
| 6A | Early Oracle dialect tests (conditional availability) | Company-approved Oracle test harness checks essential SQL semantics; absence logged blocker before Oracle-dependent release |
| 8A | Fallback operation-class gate | Only approved analytic operator classes tested with golden results; otherwise disabled |
| 10A | Ablations A–G + model benchmarking | Paired correctness/coverage/latency report; signed promotion decisions |
| 11A | Office-only catalog reconciliation | Approved physical schema and view maps, VPD/grants, time rules and business owner signoff |
**Important:** Phase 11 remains full *enterprise integration*, but Oracle dialect compatibility must not be deferred until then when test access is available. If access is blocked, implement abstract dialect tests locally and record an explicit release blocker. Don't pretend SQLite alone validates Oracle. Start with a narrow domain end to end, not all empty placeholder folders.

---

## Deliverables / artifacts to review

12-phase roadmap, dependency graph, sprint-ready ticket template, review gates, rollback and go/no-go criteria

## Acceptance tests and exit criteria

Each phase passes fixture and contract tests; no implicit leap to office DB; documented rollback

## Open decisions and evidence required

How many developers? Prioritized business metrics? Company release governance and office access dates?

## Related documents

[01](./01_SCOPE_PRD_AND_NFR.md), [03](./03_SYSTEM_ARCHITECTURE_AND_RUNTIME.md), [24](./24_TEST_DATA_EVALUATION_AND_BENCHMARKS.md), [26](./26_DOCUMENT_APPROVAL_RACI_AND_OPEN_DECISIONS.md)


---

## Historical V4 Baseline Requirements (reference only; superseded where V4.1 refines them)

> **Historical UI exclusion:** Any older requirement below to create a React/TypeScript/Vite frontend, new browser pages, screens, or UI build/test pipeline is superseded by the user decision. These are historical notes, **not implementation tasks**. Preserve existing capabilities for later integration via document 35.

> This is preserved from the earlier planning draft for comparison. The current V4.1 design section, companion docs 30–34, the approved ADR register, and subsequent validated contracts take precedence on changes explicitly addressed in the V4.1 refinement. Historical descriptions of optional vector providers, open SQL fallback, and late Oracle tests are **not** new mandatory decisions.


The following material records relevant requirements from the previously agreed V4 blueprint. The sections above are the detailed module design and take precedence where they add stricter controls. Original V4 is a **proposed architecture**, not independently verified production source.

# 25. Detailed Implementation Roadmap

We should deliver the system in stages with measurable acceptance criteria.

## Phase 0 — Requirements and Architecture Freeze

**Goal:** Establish one consistent project specification.

Tasks:

- Confirm functional scope.
- Confirm backend-first delivery and deferred integration to the sole existing EWS HTML/CSS/JS UI; no new frontend.
- Define supported question categories.
- Define data security assumptions.
- Select the canonical query-plan contract.
- Finalize component boundaries.
- Define model-provider interface.
- Define acceptance criteria.
- Establish source/version control.
- Record architecture decisions.

**Deliverables:**

- Product requirements.
- Architecture document.
- API contracts.
- Security requirements.
- Acceptance matrix.
- Initial risks and assumptions.

**Completion gate:** All mandatory interfaces and architectural decisions are documented.

## Phase 1 — Repository and Backend Foundation

**Goal:** Start a clean, testable application.

Tasks:

- Initialize Python backend.
- Configure FastAPI.
- Add Pydantic models.
- Add environment configuration.
- Implement health endpoints.
- Add structured logging.
- Create provider interfaces.
- Set up Pytest and CI.
- Implement mock authentication.
- Add error-response standards.

**Completion gate:** Backend starts locally, tests pass and all base endpoints respond correctly.

## Phase 2 — Synthetic Database and Metadata Catalog

**Goal:** Establish an authoritative local test domain.

Tasks:

- Design synthetic relational schema.
- Create synthetic data.
- Add historical and duplicate-sensitive cases.
- Build catalog models.
- Implement metadata loader.
- Implement type and relationship validation.
- Add approved metrics.
- Add catalog versioning.
- Build catalog tests.

**Completion gate:** Metadata loads consistently; invalid definitions are rejected.

## Phase 3 — Semantic and Relationship Engine

**Goal:** Make business meaning and joins deterministic.

Tasks:

- Implement business metric registry.
- Implement synonyms and aliases.
- Implement approved relationship graph.
- Add cardinality handling.
- Add grain rules.
- Add date/effective-period rules.
- Implement join-path resolution.
- Implement ambiguity detection.

**Completion gate:** Relevant join and metric rules pass independent tests.

## Phase 4 — Retrieval Engine

**Goal:** Find correct schema objects efficiently.

Tasks:

- Build exact search.
- Add BM25.
- Build permission filtering.
- Add candidate ranking.
- Integrate graph expansion.
- Add retrieval diagnostics.
- Benchmark lexical retrieval.
- Optionally add local embeddings.
- Measure retrieval accuracy.

**Completion gate:** Retrieval quality is measured; the simplest adequate retrieval configuration is selected.

## Phase 5 — Query Planning and Fast Path

**Goal:** Support standard business questions without a model wherever possible.

Tasks:

- Define typed QueryPlan.
- Implement deterministic intent templates.
- Implement parameter validation.
- Implement query-plan validator.
- Implement clarification states.
- Add fast-path routing.
- Test supported and ambiguous questions.

**Completion gate:** Certified templates reliably create approved query plans without Gemma.

## Phase 6 — Gemma 4 12B Integration

**Goal:** Enable flexible natural-language understanding.

Tasks:

- Connect local model runtime.
- Implement provider abstraction.
- Create structured planning prompt.
- Enforce structured output.
- Implement token budgeting.
- Implement timeout handling.
- Add model telemetry.
- Test paraphrases and complex questions.
- Benchmark model alternatives.

**Completion gate:** Flexible questions produce validated structured plans at measured latency and memory cost.

## Phase 7 — SQL Compiler

**Goal:** Generate controlled SQL for supported plans.

Tasks:

- Implement filter expressions.
- Implement joins.
- Implement aggregations.
- Implement grouping.
- Implement sorting and limiting.
- Add temporal rules.
- Add metric formulas.
- Implement bind parameter generation.
- Add target-dialect support.
- Build compiler tests.

**Completion gate:** Supported query plans compile into SQL that produces the correct results on approved test fixtures.

## Phase 8 — SQL Validation and Fallback

**Goal:** Ensure unsupported requests do not bypass safety.

Tasks:

- Add SQL AST parser.
- Enforce statement allowlists.
- Validate physical identifiers.
- Validate joins.
- Validate metric semantics.
- Apply resource policies.
- Implement constrained SQL fallback.
- Implement bounded repair.
- Add adversarial security suite.

**Completion gate:** Only authorized and validated SQL reaches the database adapter.

## Phase 9 — Complete Backend Sessions and EWS Integration Adapter

**Goal:** Deliver a working chatbot product.

Tasks:

- **Do not build a chat UI.** Implement authenticated compatibility routes for the supplied EWS UI, with mock-client tests.
- Add session creation/listing/loading.
- Add response tables.
- Add clarification interface.
- Implement follow-up context.
- Add safe error messages.
- Add authentication integration.
- Add feedback mechanism.
- Implement optional speech interface.
- Run backend API/legacy contract tests now; full browser UI/API tests only at the later approved integration milestone.

**Completion gate:** A user can complete an entire conversation against synthetic data.

## Phase 10 — End-to-End Evaluation and Optimization

**Goal:** Measure the system scientifically.

Tasks:

- Run golden-question suite.
- Measure business-result accuracy.
- Compare v2-style, v3-style and v4-style execution paths.
- Compare lexical versus vector-assisted retrieval.
- Benchmark Gemma and challenger models.
- Profile stage-level latency.
- Optimize model calls and token counts.
- Test concurrency.
- Review security failures.
- Tune fallback coverage.

**Completion gate:** Reproducible evaluation results demonstrate whether the architecture meets agreed quality and performance targets.

## Phase 11 — Approved Oracle Integration

**Goal:** Connect the completed system to enterprise data safely.

Tasks:

- Confirm database ownership and permissions.
- Import approved physical metadata.
- Reconcile catalog definitions with Oracle.
- Verify business metrics with domain owners.
- Validate joins and historical rules.
- Configure the read-only query identity.
- Configure separate session/audit persistence.
- Run Oracle dialect tests.
- Run approved representative golden queries.
- Confirm data governance and security requirements.

**Completion gate:** Authorized business queries return independently verified results on enterprise test data.

## Phase 12 — Production Deployment

**Goal:** Deploy and operate reliably.

Tasks:

- Finalize inference hosting.
- Configure private networking.
- Set resource and concurrency limits.
- Enable monitoring.
- Configure backups and retention.
- Test startup and restart behavior.
- Review access controls.
- Validate operational runbooks.
- Rehearse rollback.
- Perform security review.
- Release gradually.
- Monitor accuracy and latency.

**Completion gate:** Operations, security, database and product owners approve release.

---
