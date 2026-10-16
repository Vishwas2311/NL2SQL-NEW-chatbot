# 27 — Typed Interfaces, Failure Taxonomy and Complete Worked Example

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Draft for review; no implementation or company production validation performed.  
**Document owner:** Tech lead + backend/ML  
**Gate:** P0  
**Baseline reference:** V4 research/blueprint supplied on 2026-10-15.  
**Data policy:** Fictional examples only; actual company schema and customer data stay in approved office systems.

> **Core distinction:** this document specifies future behavior. It does not claim that these modules, controls, model benchmarks, or Oracle permissions are already deployed.

## Design specification

## Cross-component contracts
| Interface | Inputs | Success output | Failure categories |
|---|---|---|---|
| `Authz.allowed_catalog` | Signed principal, catalog version | Permission-filtered catalog | Denied/stale |
| `Grounder.retrieve` | Question, slots, principal, catalog | Grounding evidence bundle | Missing/ambiguous |
| `ValueResolver.resolve` | Allowed entity type, phrase, principal | Typed bound entity ID | Not found/ambiguous/denied |
| `JoinResolver.resolve` | Approved IDs, as-of, scope | JoinPlan + grain proof | Missing edge/multiplicity |
| `SLM.plan` | Grounded context, history slots | QueryPlanDraft | Invalid JSON/timeout |
| `PlanValidator.check` | Draft, immutable catalog, principal | ValidatedPlan | Semantic/policy failure |
| `Compiler.compile` | ValidatedPlan | CompiledQuery | Unsupported operation |
| `Fallback.generate` | ValidatedPlan, allowed context | SqlDraft | Timeout/invalid SQL |
| `SQLValidator.check` | Candidate SQL + proof | ValidatedQuery | Invalid/deny |
| `Preflight.execute` | ValidatedQuery + principal | Typed result | Cost/time/cancel/DB |
| `Formatter.format` | Execution result + manifest | AnswerEnvelope | Missing results/warnings |

## Worked example (fictional retail)
Question: “For 2025, show top five regions by net sales on completed orders.”
1. Auth grants allowed retail views/metric.
2. Exact/BM25 recognizes “net sales” and “regions”; embedding not required.
3. Catalog resolves certified `net_sales` metric, fiscal calendar and `region` dimension.
4. Join graph returns `orders -> customer -> region` with complete key predicates and grain proof.
5. Typed plan is generated from strict template or 1 SLM call, e.g. metric `net_sales`, dimension `region`, year `2025`, sort DESC, limit 5.
6. Plan validator checks certified formula, period, dimension compatibility, role and row limit.
7. Compiler builds Oracle-compatible parameterized aggregate, including mandatory completed-order filter and preaggregation where required.
8. Validator checks AST/joins/formula/permissions, issues opaque authorization capability.
9. Oracle preflight accepts resource budget and execution returns five typed rows with reporting period.
10. Formatter displays rows and units plus data freshness if available. Audit links catalog and query digests.

## Error mapping
Internal reason codes and public safe statuses are separate. `UNAUTHORIZED_OBJECT` -> generic denied; `MULTIPLE_METRIC_MATCHES` -> clarification; `METRIC_UNCERTIFIED` -> unsupported; `SQL_COST_TOO_HIGH` -> resource limit; `MODEL_TIMEOUT` -> temporarily unavailable; `DATA_FRESHNESS_UNKNOWN` -> successful answer with explicit unknown freshness where policy permits.

## Contract invariants
Unknown IDs never coerce to raw table names; filters always typed; authorization never from model; one catalog snapshot per request; result includes limit status; executor cannot accept unvalidated SQL; clarification reruns permission checks.



## V4.1 cross-component contract additions
| Contract | Required additions | Failure behavior |
|---|---|---|
| `SemanticViewDefinition` | ID/version, grain, dimensions, metrics, lineage, required joins/filters, time and policy roles | reject activation if uncertified |
| `GroundingBundle` | approved view IDs, lexical/vector provenance, required dependency completeness, principal/cat snapshot | ambiguous / unsupported |
| `ValidatedPlan` | chosen semantic view/version, metric IDs, typed operators, resolved values, policy digest, as-of time role | no raw owner/table/SQL input |
| `CompiledQueryProof` | plan/view hash, stable join edges, grain proof, required filters, AST digest, bind schema | compiler capability miss, not SQL draft |
| `ValidatedQuery` | opaque capability bound to principal, plan, SQL, policy, snapshot, expiry | reject unsigned/stale/unauthorized |
| `AnswerEnvelope` | reporting as-of, source refreshed-at or unknown, truncation, metric display, safe lineage ref | never invent freshness |
The fast template route also creates a full validated plan and compiled-query proof; it does not execute raw SQL behind the validator. The fallback receives the same `ValidatedPlan` and must meet approved operation class checks. Sample fictional trace: `question -> certified metric/view -> typed plan -> compile -> validate -> preflight -> typed response` with version consistency asserted at each edge.

---

## Deliverables / artifacts to review

Interface signatures, error-to-HTTP table, fictional example trace, versioned JSON schemas for implementation

## Acceptance tests and exit criteria

Contract fixtures validate every handoff; state machine cannot bypass validator; complete approved synthetic query result

## Open decisions and evidence required

Who will own schema evolution and JSON contracts? Is public SQL explanation allowed?

## Related documents

[03](./03_SYSTEM_ARCHITECTURE_AND_RUNTIME.md), [08](./08_ENTITY_AND_VALUE_RESOLUTION.md), [09](./09_ROUTING_CONFIDENCE_AND_EXECUTION_PATHS.md), [10](./10_QUERY_PLAN_DSL_AND_VALIDATION.md), [11](./11_LOCAL_SLM_MODEL_CONTEXT_AND_RUNTIME.md), [12](./12_DETERMINISTIC_SQL_COMPILER_AND_TEMPLATES.md), [13](./13_COMPLEX_SQL_FALLBACK_AND_REPAIR.md), [14](./14_SQL_VALIDATION_POLICY_AND_SECURITY.md), [15](./15_ORACLE_ADAPTER_PREFLIGHT_AND_RESOURCES.md), [16](./16_API_AUTH_AND_ERROR_CONTRACTS.md), [19](./19_RESULT_PROVENANCE_FRESHNESS_AND_EXPLANATIONS.md)


---

## Historical V4 Baseline Requirements (reference only; superseded where V4.1 refines them)

> **Historical UI exclusion:** Any older requirement below to create a React/TypeScript/Vite frontend, new browser pages, screens, or UI build/test pipeline is superseded by the user decision. These are historical notes, **not implementation tasks**. Preserve existing capabilities for later integration via document 35.

> This is preserved from the earlier planning draft for comparison. The current V4.1 design section, companion docs 30–34, the approved ADR register, and subsequent validated contracts take precedence on changes explicitly addressed in the V4.1 refinement. Historical descriptions of optional vector providers, open SQL fallback, and late Oracle tests are **not** new mandatory decisions.


The following material records relevant requirements from the previously agreed V4 blueprint. The sections above are the detailed module design and take precedence where they add stricter controls. Original V4 is a **proposed architecture**, not independently verified production source.

# 2. Final System Architecture

## 2.1 Architectural principle

The chatbot will have three main responsibilities:

**Language understanding:** The SLM interprets the user's question.

**Query correctness:** Verified metadata, business definitions, relationship rules and SQL compilation determine how the answer should be obtained.

**Secure execution:** Independent validators and Oracle database permissions determine whether a query may execute.

These responsibilities must remain separate.

## 2.2 High-level system layers

| Layer | Component | Responsibility |
|---|---|---|
| 1 | Supplied existing UI (later) | Backend contract compatibility only; no new UI deliverable |
| 2 | API Gateway | Authentication, authorization, validation and request handling |
| 3 | Conversation Manager | Chat history, follow-up context and session ownership |
| 4 | Intent Router | Determine question type and processing route |
| 5 | Semantic Catalog | Store authoritative definitions of business terms |
| 6 | Retrieval Engine | Select relevant business and physical metadata |
| 7 | Relationship Resolver | Find approved table joins and constraints |
| 8 | SLM Service | Translate flexible questions into structured query plans |
| 9 | Query Plan Validator | Verify requested metrics, filters, dates and dimensions |
| 10 | SQL Compiler | Generate SQL deterministically for supported query types |
| 11 | SQL Fallback Generator | Generate constrained SQL for supported complex cases |
| 12 | SQL Validator | Verify syntax, schema, semantics, access and execution policy |
| 13 | Database Executor | Execute authorized read-only Oracle SQL |
| 14 | Result Processor | Format data and produce understandable responses |
| 15 | Observability | Record operational metrics, errors and audit events |

## 2.3 Request processing versus metadata preparation

The system must have two separate workflows.

**Offline metadata preparation**

Approved schema metadata → normalize definitions → verify business relationships → create metadata catalog → build search indexes → publish versioned snapshot.

**Online question processing**

Question → find relevant metadata → create query plan → compile SQL → validate → execute → answer.

This separation is essential for performance.

The system should never rebuild the metadata catalog, embedding index or relationship graph every time someone asks a question.

---

---

# 3. Three Query Execution Paths

The architecture will support three paths.

## Path A — Deterministic fast path

Used when the user asks a question that unambiguously matches an approved query template or certified metric operation.

**Flow:**

User question → exact intent match → validated parameters → approved query template → SQL validation → Oracle → answer.

**Gemma calls:** Zero.

Example:

"Show the latest five reporting periods."

If an approved query template already supports this operation, the system can execute it without invoking the SLM.

### Requirements

- Match only approved templates.
- Extract and validate parameters.
- Confirm required user permissions.
- Verify the current catalog/template version.
- Never confuse a merely similar question with a certified match.
- Route ambiguous wording to the normal path.

This path is intended to minimize latency for frequent queries.

## Path B — Structured SLM planning

This is our default path for flexible business questions.

**Flow:**

Question → semantic retrieval → verified relationships → Gemma generates structured plan → validate plan → SQL compiler → validate SQL → Oracle → answer.

Example:

"Find the top ten customers with the highest exposure last quarter."

Gemma selects an approved metric, grouping, filters, sorting and limit.

The SQL compiler determines the actual Oracle tables, joins, formulas and SQL syntax.

### Benefits

- Less SQL text generated by Gemma.
- Better consistency across repeated queries.
- Easier validation.
- Less dependence on the model knowing Oracle-specific syntax.
- Easier model replacement.
- Clearer debugging when the answer is incorrect.

## Path C — Constrained complex SQL fallback

Some queries require operations outside the deterministic compiler's supported scope.

Examples may include complex analytic windows, unusual correlated subqueries or specialized temporal analysis.

**Flow:**

Question → verified grounding → structured plan → compiler reports unsupported operation → constrained SLM SQL generation → independent validation → Oracle → answer.

### Strict rules

- The model may reference only authorized, approved database objects.
- Required business formulas must come from the semantic catalog.
- The model cannot invent joins or new metric definitions.
- Generated SQL must pass all normal validation.
- Retries must be bounded.
- Unsupported or ambiguous cases must be clarified or rejected.

**Important:** Fallback exists for SQL-expression flexibility, not to bypass governance or missing business definitions.

---

---

# 10. Typed Query Plan Validation

Before generating SQL, validate the plan.

## 10.1 Plan validation requirements

| Check | Purpose |
|---|---|
| JSON structure | Verify valid typed request |
| Catalog version | Ensure matching metadata |
| Metric existence | Prevent invented metrics |
| Dimension compatibility | Prevent invalid groupings |
| Filter compatibility | Prevent unsupported comparisons |
| Date semantics | Preserve reporting-period correctness |
| Relationship coverage | Ensure approved join paths |
| Grain | Avoid incorrect aggregation |
| Permissions | Prevent unauthorized access |
| Resource policy | Bound limits and complexity |

## 10.2 Invalid plan handling

The validation engine returns structured error codes.

Examples:

- `UNKNOWN_METRIC`
- `UNKNOWN_DIMENSION`
- `UNSUPPORTED_FILTER`
- `INVALID_JOIN_PATH`
- `GRAIN_CONFLICT`
- `MISSING_TIME_DEFINITION`
- `UNAUTHORIZED_OBJECT`
- `UNSUPPORTED_OPERATION`

For a correctable structural error, the SLM may receive one bounded repair opportunity.

For unresolved business meaning or unauthorized access, do not retry until the model invents an acceptable answer.

---

---

# 13. Independent SQL Validation

This component is mandatory for every SQL path, including trusted templates.

The validator must be independent of Gemma.

## 13.1 Validation stages

| Stage | Validation |
|---|---|
| 1 | Parse SQL into an abstract syntax tree |
| 2 | Verify permitted statement types |
| 3 | Verify allowed Oracle objects |
| 4 | Verify column identifiers |
| 5 | Verify approved relationships |
| 6 | Verify business metric usage |
| 7 | Verify grouping and aggregation grain |
| 8 | Verify time and effective-date rules |
| 9 | Verify authorization constraints |
| 10 | Verify parameter binding |
| 11 | Apply resource limits |
| 12 | Produce authorized execution request |

## 13.2 Prohibited behavior

Initial policy should prohibit:

- INSERT, UPDATE, DELETE and MERGE.
- CREATE, DROP, ALTER and TRUNCATE.
- Anonymous PL/SQL.
- Administrative operations.
- Stored procedure or database function calls unless specifically vetted.
- Unapproved remote database links.
- Unapproved tables, views or synonyms.
- Multiple SQL statements.
- Side-effecting functions.
- Attempts to bypass access controls.
- Queries exceeding resource restrictions.

## 13.3 SQL semantic validation

Parsing alone cannot verify correctness.

We must also ensure:

- A metric uses its approved formula.
- Customer counts do not double count.
- Snapshot selection is correct.
- Required filters are present.
- Date boundaries are interpreted correctly.
- Join predicates are complete.
- Restricted columns are not exposed.
- A user's requested grouping is compatible with the metric.

## 13.4 Resource protection

Configure:

- Maximum returned rows.
- Statement execution timeout.
- Query concurrency limit.
- Statement complexity restrictions.
- Safe pagination.
- Maximum response size.
- Database resource policies.
- Optional database-side query-cost controls.

These values must be configurable and tested against the actual enterprise environment.

## 13.5 Validation result

Return an explicit decision:

- `APPROVED`
- `REPAIRABLE`
- `CLARIFICATION_REQUIRED`
- `UNSUPPORTED`
- `REJECTED_SECURITY`
- `REJECTED_RESOURCE`
- `INVALID_SQL`

Only `APPROVED` requests may reach the executor.

---

---

# 16. Backend API Design

Use FastAPI with versioned public endpoints for the new application.

## 16.1 Core API endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/health/live` | GET | Process liveness |
| `/api/v1/health/ready` | GET | Dependency readiness |
| `/api/v1/chat` | POST | Submit natural language query |
| `/api/v1/sessions` | POST | Create chat session |
| `/api/v1/sessions` | GET | List owned sessions |
| `/api/v1/sessions/{id}` | GET | Load session |
| `/api/v1/sessions/{id}` | DELETE | Delete owned session |
| `/api/v1/sessions/{id}/messages` | GET | Retrieve history |
| `/api/v1/feedback` | POST | Record feedback |
| `/api/v1/queries/{id}/cancel` | POST | Cancel a supported running query |
| `/api/v1/speech/transcriptions` | POST | Optional speech transcription |

Administration endpoints, if needed, should be separately authorized and isolated from ordinary users.

## 16.2 Chat request

Example:

```json
{
  "session_id": "optional-session-id",
  "message": "Show top ten customers by exposure",
  "client_request_id": "request-123"
}
```

The authenticated user identity must come from validated authentication credentials, not from a client-supplied `user_id`.

## 16.3 Chat response

Example:

```json
{
  "session_id": "session-123",
  "message_id": "message-456",
  "status": "completed",
  "response": "Here are the matching results.",
  "result": {
    "type": "table",
    "columns": ["customer", "exposure"],
    "rows": []
  },
  "query_reference": "query-789",
  "warnings": [],
  "requires_clarification": false
}
```

The exact public API schema should be versioned and tested.

## 16.4 Existing office compatibility

At the approved later UI integration, the backend must provide an adapter preserving all observed EWS routes and response fields from document 35.

The reported existing routes include:

- `/ews-chatbot/chat`
- `/ews-chatbot/get_all_sessions`
- `/ews-chatbot/load_session/{session_id}`
- `/ews-chatbot/delete_session/{session_id}`
- `/health`

Compatibility is verified against the uploaded UI files and authorized backend contract tests; office environment behavior remains to be established.

Do not force new frontend changes merely to accommodate internal backend restructuring.

---

---

# 18. Result Processing and Answer Generation

## 18.1 Result formatting

The result processor must convert typed database output into user-friendly content.

Supported formats:

- Single values.
- Tables.
- Ranked lists.
- Time-series summaries.
- Comparisons.
- Simple charts.
- No-data explanations.

## 18.2 Do we need Gemma to explain results?

Not always.

For standard results, deterministic templates are sufficient.

Example:

"Ten matching customers were found for the selected period."

For complex interpretations, Gemma may generate a natural language summary from approved, minimized result data.

The generated summary must not invent facts or make unsupported business judgments.

## 18.3 Result quality checks

Verify:

- Expected columns are returned.
- Numeric values retain precision.
- Dates are formatted correctly.
- Units and currencies are clear.
- Truncation is disclosed.
- Empty results are not described as execution failures.
- Restricted values are not exposed.

## 18.4 Chart generation

Use deterministic chart specifications based on result types and approved presentation rules.

A language model should not invent chart data.

---
