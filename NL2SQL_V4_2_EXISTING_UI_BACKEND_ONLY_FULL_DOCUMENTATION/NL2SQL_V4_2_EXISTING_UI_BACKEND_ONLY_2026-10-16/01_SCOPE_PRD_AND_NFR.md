# 01 — Product Scope, PRD and Nonfunctional Requirements

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Draft for review; no implementation or company production validation performed.  
**Document owner:** Product owner + architect  
**Gate:** P0  
**Baseline reference:** V4 research/blueprint supplied on 2026-10-15.  
**Data policy:** Fictional examples only; actual company schema and customer data stay in approved office systems.

> **Core distinction:** this document specifies future behavior. It does not claim that these modules, controls, model benchmarks, or Oracle permissions are already deployed.

## Design specification

## Product statement
Build an authenticated private enterprise analytics chatbot for authorized, read-only questions about approved Oracle data. A user supplies natural language; the system chooses a certified template, a typed semantic plan, or a controlled SQL fallback, executes only validated queries, and returns an intelligible result with period, units and provenance. The application includes its own backend services, session management, monitoring, administrative catalog publication and test harness. The user-supplied EWS HTML/CSS/JavaScript UI is the fixed product interface, to be integrated later through mandatory compatibility endpoints. No new UI is in scope.

## Personas and job-to-be-done
| Persona | Primary goal | Important constraint |
|---|---|---|
| Analyst | Filter, compare and summarize governed metrics | Correct grain, time, permissions |
| Operational user | Ask recurring reporting questions | Fast and explainable answers |
| Domain steward | Certify metrics, terminology and sources | Every definition versioned and approved |
| DBA | Safeguard Oracle workload and rights | Least-privilege execution |
| Security reviewer | Validate identity, audit and egress | No unapproved access or data export |
| ML/Platform engineer | Maintain local model and inference capacity | Predictable resources and fallback |

## Functional requirement baseline
| ID | Requirement | Priority | Verification |
|---|---|---|---|
| F-01 | Login, logout and per-user chat sessions | P0 | Contract + cross-user isolation tests |
| F-02 | Text-to-query for approved lookup, aggregate, rank, trend, comparison | P0 | Golden questions with verified results |
| F-03 | Follow-up questions can refer to prior authorized context | P0 | Multi-turn regression set |
| F-04 | Unsupported/ambiguous business questions lead to clarification, not guesses | P0 | Negative and ambiguous set |
| F-05 | Return explicit period, units and truncation/freshness context | P0 | Response schema assertions |
| F-06 | Read-only Oracle execution with timeouts and parameterization | P0 | Security and Oracle integration suite |
| F-07 | Support tabular results with stable pagination/cancellation rules | P0 | UI/API tests |
| F-08 | Opt-in CSV export / chart / speech, only if approved | P1 | Feature-gated tests |
| F-09 | Feedback on incorrect answers linked to non-sensitive query reference | P1 | Audited feedback flow |
| F-10 | Administrative publication of catalog versions | P0 | Approve/publish/rollback tests |

## Nonfunctional principles
- Correctness and authorization outrank latency. A quick wrong answer is a failure.
- Model inference stays inside approved infrastructure. No external LLM or embedding service is necessary.
- The web UI and FastAPI backend have versioned contracts; no direct frontend-to-Oracle or frontend-to-model access.
- Default to a modular monolith; move inference to a separate internal service when required by hardware/concurrency.
- Do not claim latency SLOs until load tests on target hardware; choose measured p50/p95 objectives in sign-off.
- Define retention, accessibility, peak concurrency, recovery and availability targets with product/operations owners.

## Explicitly deferred
Public sharing, database modifications, arbitrary file retrieval, online schema crawls during chat, unmanaged multi-agent tool invocation, mandatory Neo4j/Graphify/Qdrant, and automatic training from users' prompts.

## Requirement traceability
Use IDs `F-*` (function), `N-*` (nonfunctional), `S-*` (security), `E-*` (evaluation). Every delivery PR should state requirements implemented, unit tests, integration tests, failure behavior and status; see acceptance gates in document 25.



## V4.1 product requirements — governed semantic-view coverage
- **PRD-VIEW-01:** The user may ask questions mapped to *certified* semantic views. Display the period, units, scope, freshness and whether results are truncated; preserve a safe source/metric explanation without exposing restricted physical SQL objects.
- **PRD-COV-01:** Report valid-question coverage and correct-answer accuracy jointly; a fast path that rejects difficult valid questions must not be declared superior on accepted-only accuracy.
- **PRD-CLAR-01:** Ambiguous metrics, unmatched entity values, undefined time defaults, and conflicting temporal view versions return a typed clarification or unsupported outcome, never silent best-guess SQL.
- **PRD-PORT-01:** Synthetic development and approved enterprise Oracle use the same typed catalog/DSL/compiler contracts through provider adapters; no real company schema copied to unauthorized workspaces.
- **PRD-FALL-01:** Restricted complex SQL fallback is off by default in production until a reviewed operation allowlist and domain-level execution golden tests pass.
- **PRD-SLO-01:** Latency, coverage, model calls, query-cost and concurrency budgets are measurable acceptance values to be signed off, not fabricated targets.
See [31](./31_GOVERNED_SEMANTIC_VIEWS_AND_COVERAGE.md), [32](./32_RETRIEVAL_TECH_CHOICES_AND_EXPERIMENTS.md), [33](./33_ORACLE_EARLY_COMPATIBILITY_AND_PREFLIGHT.md).

---

## Deliverables / artifacts to review

PRD, prioritized backlog, persona acceptance tests, measurable NFR register, in/out scope

## Acceptance tests and exit criteria

Authenticate; basic/complex/ambiguous/disallowed queries; new and follow-up sessions; no sensitive leakage in output

## Open decisions and evidence required

UI reuse is decided; open: Who owns NFR targets? Does production permit export and optional speech? Which identity approach secures the existing browser contract?

## Related documents

[02](./02_USER_JOURNEYS_AND_INTENTS.md), [03](./03_SYSTEM_ARCHITECTURE_AND_RUNTIME.md), [16](./16_API_AUTH_AND_ERROR_CONTRACTS.md), [17](./17_FRONTEND_UX_RESULT_TABLES_AND_ACCESSIBILITY.md), [21](./21_SECURITY_PRIVACY_THREAT_MODEL.md), [25](./25_IMPLEMENTATION_ROADMAP_DEPENDENCIES_AND_GATES.md)


---

## Historical V4 Baseline Requirements (reference only; superseded where V4.1 refines them)

> **Historical UI exclusion:** Any older requirement below to create a React/TypeScript/Vite frontend, new browser pages, screens, or UI build/test pipeline is superseded by the user decision. These are historical notes, **not implementation tasks**. Preserve existing capabilities for later integration via document 35.

> This is preserved from the earlier planning draft for comparison. The current V4.1 design section, companion docs 30–34, the approved ADR register, and subsequent validated contracts take precedence on changes explicitly addressed in the V4.1 refinement. Historical descriptions of optional vector providers, open SQL fallback, and late Oracle tests are **not** new mandatory decisions.


The following material records relevant requirements from the previously agreed V4 blueprint. The sections above are the detailed module design and take precedence where they add stricter controls. Original V4 is a **proposed architecture**, not independently verified production source.

# 1. Project Vision and Scope

## 1.1 What we are building

We will develop a complete, self-hosted AI chatbot that allows authorized users to ask business questions in natural language.

The system will translate those questions into database operations, retrieve data from Oracle and present the results in an understandable format.

Example questions:

- Show the ten customers with the highest outstanding exposure.
- How many customers were classified as high risk this month?
- Compare customer exposure for the last three financial years.
- Which customers have multiple active risk indicators?
- Show the latest approved risk score for a customer.
- Compare this quarter's results with the previous quarter.
- Which customers experienced the largest increase in exposure?
- Show records matching a combination of historical and current conditions.

The chatbot must understand ordinary language, business terminology, dates, aggregations, relationships and follow-up questions.

It must also recognize when it cannot safely answer a question.

## 1.2 Our primary objectives

| Objective | Requirement |
|---|---|
| SQL accuracy | Generate correct SQL using verified metadata |
| Business accuracy | Follow approved definitions, aggregation rules and reporting periods |
| SLM efficiency | Minimize model calls, prompt size and generated tokens |
| Privacy | Keep inference and sensitive information in approved private infrastructure |
| Database security | Execute only authorized read-only business queries |
| Flexibility | Support both standard reports and complex SQL questions |
| Performance | Avoid unnecessary database, graph, retrieval and model operations |
| Scalability | Support concurrent users without redesigning the application |
| Maintainability | Separate model, retrieval, business logic and database components |
| Portability | Support different approved model runtimes and environments |
| Observability | Identify exactly where failures and latency occur |
| Testability | Run the application independently against synthetic datasets |

## 1.3 Two development environments

**Environment A — Local development**

We will use fictional schemas, synthetic records, local metadata and SQLite or another approved lightweight test database.

The entire backend business logic, retrieval, graph, planner, SQL compiler, validator, sessions and mock-client API flow should be testable here; existing UI integration is deferred.

**Environment B — Approved enterprise deployment**

The application will connect to the organization's approved Oracle database and self-hosted inference infrastructure.

Actual schema metadata, business rules, permissions and deployment configuration must be validated in the enterprise environment.

No real Oracle access is required to develop the initial system.

## 1.4 Non-goals for the initial version

We will not initially build:

- A Neo4j database server.
- A second dedicated vector database platform.
- A complex multi-agent architecture.
- An unrestricted autonomous SQL execution agent.
- A universal SQL compiler supporting every Oracle feature.
- A full model-training or fine-tuning platform.
- Continuous live database schema introspection for every request.
- Automatic modification of the production database.

These capabilities can be reconsidered when evaluation demonstrates a genuine need.

---

---

# 28. Decisions We Are Locking

| Architecture question | Final decision |
|---|---|
| Build NL-to-SQL backend from scratch, reuse existing UI later? | Yes |
| Backend framework | FastAPI |
| Frontend | Existing user-provided HTML + CSS + JavaScript, integrated later; do not rebuild |
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

---

# 29. Definition of a Completed Application

The project is complete only when the following conditions are met.

## Product

- Users can authenticate.
- Users can ask natural language questions.
- Users can create and load conversations.
- Users can ask follow-up questions.
- Users can see correctly formatted results.
- Ambiguous questions produce clarifications.
- Unsupported questions produce safe responses.
- Users cannot access another user's private sessions.

## Query intelligence

- Relevant metadata is retrieved.
- Business definitions are resolved correctly.
- Joins use approved relationships.
- Gemma produces valid query plans within the tested scope.
- Standard supported SQL is compiled deterministically.
- Complex supported SQL uses controlled fallback.
- Invalid or unauthorized queries do not execute.

## Database

- Oracle queries use approved read-only permissions.
- Bind parameters are enforced.
- Query limits and timeouts work.
- Connection pooling works.
- Historical and aggregation rules are tested.
- Database errors are safely handled.

## Performance

- Stage-level latency is measured.
- Token usage is monitored.
- Model calls are minimized where possible.
- Concurrency is tested.
- Memory utilization is recorded.
- Caching respects security and freshness.

## Security and operations

- Independent security tests pass.
- Sensitive data stays within approved boundaries.
- Catalog and model versions are traceable.
- Logs are appropriately redacted.
- Production monitoring is active.
- Deployment and rollback procedures are documented.

## Evaluation

- Supported-query coverage is reported.
- Business-result accuracy is measured.
- SQL and join accuracy are measured.
- Safe rejection is tested.
- Performance is benchmarked.
- Significant regressions block release.

---

---

# 30. Final Engineering Strategy

The application must not become complicated merely because additional AI technologies exist.

We should optimize for the complete request, not only SLM inference.

A system that produces SQL very quickly but calculates incorrect business values is not successful.

A system that returns correct answers only for ten predefined questions is not sufficient for a flexible enterprise chatbot.

A system that relies on the model to invent every join and business formula will be difficult to govern.

Our chosen architecture balances these concerns.

**For easy questions:** use certified templates and avoid model inference.

**For normal questions:** use Gemma to produce a structured plan and deterministic software to generate SQL.

**For complex questions:** use constrained model-generated SQL only when necessary and allowed.

**For every question:** enforce verified metadata, authorization, query safety and correct business semantics.

The final guiding principle is:

**Natural language understanding belongs to the SLM. Business meaning belongs to the semantic catalog. SQL construction belongs to the compiler where possible. Permissions and safe execution belong to independent software and Oracle.**

This is the definitive v4 implementation target. Its real accuracy, latency and resource advantages must be established through controlled benchmarks during development.
