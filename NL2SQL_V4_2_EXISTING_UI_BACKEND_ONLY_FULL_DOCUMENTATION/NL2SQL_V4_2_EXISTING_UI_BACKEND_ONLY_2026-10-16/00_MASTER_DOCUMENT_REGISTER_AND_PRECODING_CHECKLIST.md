# 00 — V4.1 Master Document Register and Pre-Coding Approval Checklist

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Project:** Private Enterprise NL-to-SQL Chatbot — V4.1 Refined (preserves seven V4 improvements)  
**Initial source:** 2026-10-15 · **Refined:** 2026-10-16  
**Scope:** New NL-to-SQL **backend** from scratch, synthetic-first, private Oracle integration; supplied existing browser UI is reused later, with no frontend rebuild.  
**Current phase:** ARCHITECTURE + DOCUMENTATION ONLY. **No application code has been implemented in this pack.**

## What this package is
This is a complete **pre-development design pack**, not deployed software or source-code verification. It builds on the previously supplied V4 blueprint and newly incorporates: secure value/entity resolver; confidence and ambiguity gate; Oracle cost preflight; answer provenance/freshness; Oracle-specific test gates; explicit performance budgets; accuracy-versus-coverage measurement. Graphify and separate Neo4j/Qdrant/Milvus servers are **optional**. Verified joins can use an in-memory graph, and embeddings are conditional. The company Oracle physical catalog must be verified internally.

## Final architecture in one line
Authenticated question → policy-scoped semantic/lexical (optional vector) grounding → verified value and join resolution → 0-call certified template OR one-call typed Gemma plan → deterministic SQL compiler (restricted fallback only when supported) → independent SQL/business/policy checks → Oracle preflight → authorized read-only execution → answer with provenance and freshness.



## V4.1 refinement — read this first
**Status: proposed engineering baseline, not company-approved or benchmark-proven.** The full package was reviewed against the previous 30 numbered designs. This release adds one unambiguous architecture, formal semantic-view contracts, bounded lexical/vector experiments, a restricted SQL fallback grammar, early Oracle compatibility checks, and professional coding/CI standards. The **same canonical certified catalog** remains authoritative; a business semantic view is an abstraction over it, not an independent source of truth. No unapproved Graphify, spreadsheet, or schema sample is considered certified.

**Canonical request sequence:** authenticated request → scope-filtered business domain / approved metrics → deterministic fast route or adaptive lexical retrieval (optional local vector) → permitted semantic view/verified physical relationships and secure value resolution where needed → Gemma typed plan if needed → semantic plan validation → compiler-first SQL (narrow fallback only if authorized) → independent policy + AST + semantic validation → Oracle resource preflight → read-only Oracle execution → provenance-aware answer. An ambiguous or denied request exits before SQL execution.

**Authoritative new companion documents:** [30 Coding and Codex Standards](./30_CODING_STANDARDS_CODEX_AND_CI.md), [31 Governed Semantic Views](./31_GOVERNED_SEMANTIC_VIEWS_AND_COVERAGE.md), [32 Retrieval/Graph Technology and Ablations](./32_RETRIEVAL_TECH_CHOICES_AND_EXPERIMENTS.md), [33 Oracle Dialect and Preflight Qualification](./33_ORACLE_EARLY_COMPATIBILITY_AND_PREFLIGHT.md), [34 Release Traceability and Finalization](./34_TRACEABILITY_DECISIONS_AND_FINAL_REVIEW.md). Update/approve corresponding ADRs in document 28 and reviewer decisions in 26 before moving into controlled enterprise integration.

**The first implementation milestone remains a synthetic-only, tested vertical slice** with explicit limitations. 'Production ready', verified Oracle compatibility, latency gains and model superiority are not claims made by this document pack.

---


## V4.2 selected UI and retained scope
**User-selected final UI:** provided `index.html` + `script.js` + `style.css`, unchanged as product choice. No new frontend code shall be built. Backend/API, models, retriever, semantic catalog/views, join graph, compiler, validators, Oracle and data tests remain specified as V4.1. Exact existing wire shapes and later approved security/integration gates: [35](./35_EXISTING_UI_INTEGRATION_CONTRACT.md).

## Required documents and review owners
| # | Document | Priority | Owner(s) | Main deliverable | Approval |
|---|---|---|---|---|---|
| 01 | [Product Scope, PRD and Nonfunctional Requirements](./01_SCOPE_PRD_AND_NFR.md) | P0 | Product owner + architect | PRD | Draft |
| 02 | [User Journeys, Intent Types and Conversation UX](./02_USER_JOURNEYS_AND_INTENTS.md) | P0 | Product + UX + domain owner | Journey map | Draft |
| 03 | [System Architecture, Sequence and Trust Boundaries](./03_SYSTEM_ARCHITECTURE_AND_RUNTIME.md) | P0 | Solution architect | Logical/component/deployment diagrams | Draft |
| 04 | [Certified Semantic Catalog and Metric Governance](./04_SEMANTIC_CATALOG_AND_GOVERNANCE.md) | P0 | Domain owners + data engineering | Versioned catalog schema | Draft |
| 05 | [Metadata Ingestion, Verification, Index Publishing and Drift](./05_METADATA_INGESTION_AND_RECONCILIATION.md) | P0 | Data engineer + DBA | Import adapters | Draft |
| 06 | [Permission-Aware Retrieval, Keyword Search and Optional Vectors](./06_RETRIEVAL_LEXICAL_VECTOR_AND_RANKING.md) | P0/P1 | AI search engineering | Lexical index | Draft |
| 07 | [Verified Join Graph, Aggregation Grain and Temporal Correctness](./07_JOIN_GRAPH_GRAIN_AND_TEMPORAL_RULES.md) | P0 | DBA + data engineering | Graph node/edge types | Draft |
| 08 | [Secure Entity, Identifier and Filter-Value Resolution](./08_ENTITY_AND_VALUE_RESOLUTION.md) | P0 | Backend + security + domain owner | Value resolver protocol | Draft |
| 09 | [Intent Routing, Confidence Gates and Three-Path Decisions](./09_ROUTING_CONFIDENCE_AND_EXECUTION_PATHS.md) | P0 | AI engineer + backend architect | Routing state machine | Draft |
| 10 | [Typed Query DSL, Pydantic Models and Plan Validation](./10_QUERY_PLAN_DSL_AND_VALIDATION.md) | P0 | Backend + data engineering | QueryPlan JSON schema | Draft |
| 11 | [Gemma 4 12B, Model Adapters, Prompt/Context and Runtime](./11_LOCAL_SLM_MODEL_CONTEXT_AND_RUNTIME.md) | P0 | ML engineering + platform | Provider contract | Draft |
| 12 | [Semantic SQL Compiler, Templates and Oracle Dialect](./12_DETERMINISTIC_SQL_COMPILER_AND_TEMPLATES.md) | P0 | Backend compiler team + DBA | Relational intermediate representation | Draft |
| 13 | [Restricted SLM SQL Fallback, Correction and Abstention](./13_COMPLEX_SQL_FALLBACK_AND_REPAIR.md) | P1 | ML + backend security | Fallback allowlist | Draft |
| 14 | [Independent SQL AST, Semantic and Authorization Validator](./14_SQL_VALIDATION_POLICY_AND_SECURITY.md) | P0 | Backend security + DBA | ValidatedQuery capability | Draft |
| 15 | [Oracle Adapter, Secure Entity Lookup, Query Preflight and Resource Budgets](./15_ORACLE_ADAPTER_PREFLIGHT_AND_RESOURCES.md) | P0 | DBA + backend + security | Oracle adapter protocol | Draft |
| 16 | [Versioned API, Authentication, Authorization and Error Contracts](./16_API_AUTH_AND_ERROR_CONTRACTS.md) | P0 | Backend + security + frontend | OpenAPI v1 | Draft |
| 17 | [Existing UI Capability and Integration Requirements](./17_FRONTEND_UX_RESULT_TABLES_AND_ACCESSIBILITY.md) | P0 | Backend/API + UI owner | Existing UI acceptance profile | Draft |
| 18 | [Conversation Session Model, Context Carry-Forward and Retention](./18_SESSIONS_FOLLOWUP_MEMORY_AND_PERSISTENCE.md) | P0 | Backend + product + security | Session schema | Draft |
| 19 | [Result Integrity, Provenance, Freshness and Human-Readable Answers](./19_RESULT_PROVENANCE_FRESHNESS_AND_EXPLANATIONS.md) | P0 | Data + backend + UX | AnswerEnvelope schema | Draft |
| 20 | [Caching, Adaptive Retrieval, Token and Latency Budgets](./20_CACHING_LATENCY_AND_RESOURCE_BUDGETS.md) | P0/P1 | Platform + ML + backend | Span definitions | Draft |
| 21 | [Threat Model, Privacy, Policy Enforcement and Security Testing](./21_SECURITY_PRIVACY_THREAT_MODEL.md) | P0 | Security architect + DBA | Threat model | Draft |
| 22 | [Private Deployment Topology, Model Infrastructure and Fulcrum Questions](./22_PRIVATE_DEPLOYMENT_INFRA_AND_FULCRUM.md) | P0 | Platform + infrastructure + DBA | Deployment diagrams and topology options | Draft |
| 23 | [Observability, SRE Runbooks, Audit and Reliability](./23_OBSERVABILITY_SRE_AND_OPERATIONS.md) | P0 | SRE + backend/ML operations | Event/spans schema | Draft |
| 24 | [Synthetic Golden Data, Evaluation, Ablations and Quality Metrics](./24_TEST_DATA_EVALUATION_AND_BENCHMARKS.md) | P0 | QA/AI + DBA + product | Golden dataset schema | Draft |
| 25 | [Phased Delivery Roadmap, Backlog, Dependencies and Exit Gates](./25_IMPLEMENTATION_ROADMAP_DEPENDENCIES_AND_GATES.md) | P0 | Tech lead + QA + product | 12-phase roadmap | Draft |
| 26 | [Architecture Review, RACI, Decision Log and Signoff](./26_DOCUMENT_APPROVAL_RACI_AND_OPEN_DECISIONS.md) | P0 | Architect + product + DBA + security | RACI | Draft |
| 27 | [Typed Interfaces, Failure Taxonomy and Complete Worked Example](./27_TYPED_CONTRACTS_ERRORS_AND_END_TO_END_EXAMPLE.md) | P0 | Tech lead + backend/ML | Interface signatures | Draft |
| 28 | [Repo Layout, Dependency Choices, Configuration and ADRs](./28_REPOSITORY_STRUCTURE_AND_TECHNOLOGY_ADRS.md) | P0 | Tech lead + platform | Canonical repo directory tree | Draft |

| 29 | [Changelog and Evidence Register](./29_CHANGELOG_AND_EVIDENCE_REGISTER.md) | P1 | Tech lead | Audit of changes and evidence | Draft |
| 30 | [Coding Standards, Codex Workflow and CI](./30_CODING_STANDARDS_CODEX_AND_CI.md) | P0 | Tech lead + QA/security | CI quality profile + AGENTS template | Draft |
| 31 | [Governed Semantic Views, Grain and Coverage](./31_GOVERNED_SEMANTIC_VIEWS_AND_COVERAGE.md) | P0 | Domain owner + DBA | View type, certification and proof | Draft |
| 32 | [Retrieval Tech Choices and Ablation Experiments](./32_RETRIEVAL_TECH_CHOICES_AND_EXPERIMENTS.md) | P0/P1 | Search/ML + QA | FTS5 default, FAISS gate, A–G benchmark | Draft |
| 33 | [Early Oracle Compatibility and Preflight](./33_ORACLE_EARLY_COMPATIBILITY_AND_PREFLIGHT.md) | P0 | DBA + security/backend | Dialect matrix and test access gate | Draft |
| 34 | [Traceability and Final Signoffs](./34_TRACEABILITY_DECISIONS_AND_FINAL_REVIEW.md) | P0 | Architect + all owners | Impact matrix, unapproved decisions and signoffs | Draft |
| 35 | [Existing UI Integration Contract and Security Audit](./35_EXISTING_UI_INTEGRATION_CONTRACT.md) | P0 | Backend + API security + UI owner | Exact legacy routes, DTO mapping, later-integration gates | Draft |

## Recommended review order
**Stage A: scope and authority** — 01, 02, 03, 26, 28, 30, 34. Confirm fixed existing-UI compatibility boundary, security boundary, scope and deployment assumptions.

**Stage B: query correctness core** — 04, 05, 07, 08, 09, 10, 12, 14, 15, 31, 33. First ensure metrics, relationships, entity resolution, DSL, compiler and Oracle gate are precise.

**Stage C: optional AI/retrieval** — 06, 11, 13, 20, 32. Benchmark lexical/vector, model and fallback rather than accepting technology assumptions.

**Stage D: user product + operations** — 16, 17, 18, 19, 21, 22, 23. Confirm all UX, auth, privacy, runtime and support needs.

**Stage E: quality and go/no-go** — 24, 25, 27. Approve synthetic goldens, coverage/accuracy metrics, deliverable sequencing and contract examples.

## Required pre-coding sign-offs
- [x] Product direction: preserve user-provided HTML/CSS/JavaScript UI; build no replacement UI. [ ] Product/security owner approves any changes needed to make that UI production-safe.
- [ ] Domain owner approves metric definitions, fiscal conventions, reporting periods and data grain.
- [ ] DBA approves intended Oracle test environment, physical views and allowed join definitions.
- [ ] Security approves permission model, private inference, sensitive-value lookup and audit retention.
- [ ] AI/platform owner validates proposed Gemma model/runtime and hosting provision plan.
- [ ] Engineering owners approve typed QueryPlan and ValidatedQuery contracts.
- [ ] QA agrees synthetic golden dataset and mandatory safety invariants.
- [ ] Product/ops set **measured** quality/coverage, p95 latency and concurrency targets.
- [ ] Architecture review checks that Graphify/vector/Neo4j are not compulsory dependencies.
- [ ] Every P0 open question is either answered or documented as a named implementation blocker.

## Decisions already recommended (design, not measured proof)
- **V4 Hardened:** structured query plans, compiler-first SQL for supported questions, restricted fallback for SQL capability gaps.
- **Three paths:** 0-SLM certified queries, normal SLM plan, controlled complex-query fallback.
- **Retrieval:** exact/BM25 first, vectors only if evaluated benefit, principal-filter before search.
- **Graph:** versioned in-memory verified physical join graph, with grain/date safeguards.
- **Source data:** synthesized locally; approved private enterprise metadata and Oracle only in office.
- **Privacy:** private SLM/embeddings; default no sensitive customer data in vector index.
- **Safety:** SQL AST + semantic policy + least-privileged DB query identity + preflight.
- **Efficiency:** stage-level timing, bounded inference/repair, catalog precompile and scope-aware caches.

## Risks / unresolved gates (do not quietly assume answers)
1. Full Oracle schema, constraints, RLS/VPD rules and query grants are not confirmed here.
2. Company metadata completeness and certified business metric definitions are unknown.
3. Production Fulcrum/GPU/SLM placement, persistence and service rights are unverified.
4. **Resolved user choice:** reuse supplied existing UI exclusively; backend is built first; security/API integration will occur later after explicit approval.
5. Exact latency, resource quotas and coverage thresholds must be measured.
6. SLM SQL fallback operation allowlist and approved Oracle functions require DBA/security review.
7. Sharing or exporting original bank/customer metadata is outside the scope of this portable package.

## File conventions and change control
Each document states owner, gate, exact module decisions, interfaces, test evidence and unresolved questions. Draft approval is not inferred from producing a document. Update impacted API/query contracts and golden tests whenever a design changes. An ADR and signed review are necessary for any change affecting authentication, financial definitions, Oracle access or model egress.
