# 14 — Independent SQL AST, Semantic and Authorization Validator

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Draft for review; no implementation or company production validation performed.  
**Document owner:** Backend security + DBA  
**Gate:** P0  
**Baseline reference:** V4 research/blueprint supplied on 2026-10-15.  
**Data policy:** Fictional examples only; actual company schema and customer data stay in approved office systems.

> **Core distinction:** this document specifies future behavior. It does not claim that these modules, controls, model benchmarks, or Oracle permissions are already deployed.

## Design specification

## Structural and authorization gates
A single trusted validator is the only component permitted to issue `ValidatedQuery`. Accept compiler output or SLM fallback draft, parse entire statement into an Oracle-oriented AST, require exactly one allowlisted read-only query, reject DDL/DML/PLSQL, side-effecting routines, links and unapproved functions, resolve all tables/aliases and columns against the principal's approved catalog view, and verify that all user values are bound.

## Semantic validation
Compare the query's selected sources, joins, metrics, aggregation grain, period filters, temporal predicates and required row policies against the `ValidatedPlan` proof manifest. SQL parse success cannot prove arithmetic, historical or business correctness. For fallback SQL, prefer conservative allowlists over trying to infer all possible semantic equivalences.

## Enforcement boundaries
- App validator enforces approved query structure and controls.
- Oracle query identity enforces least privilege and DB-enforced row/column controls where required.
- Query preflight enforces resource restrictions before execution.
- Session writes use a separate identity and persistence path.
- UI may not submit SQL text for arbitrary execution through chat endpoint.

## Validator result states
`APPROVED`, `REPAIRABLE`, `CLARIFY`, `UNSUPPORTED`, `DENY_POLICY`, `DENY_RESOURCE`, `INVALID_AST`, `CATALOG_STALE`. Only `APPROVED` yields an opaque execution capability with scoped principal ID, SQL digest, binds, policy version, catalog digest and expiration.

## Additional threat cases
CTE alias hiding restricted table; UNION from unauthorized schema; nested query with prohibited function; comment-based prompt/SQL injection; use of a stored function with side effects inside SELECT; unbounded Cartesian joins; bypassing mandatory tenant predicate; unauthorized masking or aggregation of sensitive values; forged catalog version. Review security regression cases whenever SQL parser or database version changes.

## Negative/positive proofs
Positive: a fully certified parameterized aggregate passes and returns expected result. Negative: every forbidden construct is rejected *without a DB execute call*. Security tests should use a spy executor to establish zero invocation, not rely only on error messages.



## V4.1 semantic-view-aware SQL proofs
A query is executable only when the validator can trace its output back to a certified `SemanticViewDefinition` and authorized physical dependencies. Verify that selected columns are exported by the view; enforced metrics/date roles are unchanged; join paths, pre-aggregate order, row filters, view effective period and user grants match the original validated plan. SQLGlot AST validity is not a correctness proof; known-safe templates and supported compiler AST are independently tested against expected results.
Restricted SLM fallback must be explicitly matched to an approved operation class from [13](./13_COMPLEX_SQL_FALLBACK_AND_REPAIR.md), and denied when semantic equivalence cannot be established. For DB-managed row/column security, record enforcement assumptions and require DBA validation. The executor accepts only opaque validated capabilities tied to principal/snapshot/query digest and expiry.

---

## Deliverables / artifacts to review

ValidatedQuery capability, AST allowlist, business-semantic verifier, security tests and policy matrix

## Acceptance tests and exit criteria

Zero unsafe execution in adversarial suite, DB privileges independently restrict unauthorized access, all paths use same validator

## Open decisions and evidence required

Which views/functions/DB policies approved by DBA? What SQL features are safely executable?

## Related documents

[04](./04_SEMANTIC_CATALOG_AND_GOVERNANCE.md), [07](./07_JOIN_GRAPH_GRAIN_AND_TEMPORAL_RULES.md), [10](./10_QUERY_PLAN_DSL_AND_VALIDATION.md), [12](./12_DETERMINISTIC_SQL_COMPILER_AND_TEMPLATES.md), [13](./13_COMPLEX_SQL_FALLBACK_AND_REPAIR.md), [15](./15_ORACLE_ADAPTER_PREFLIGHT_AND_RESOURCES.md), [21](./21_SECURITY_PRIVACY_THREAT_MODEL.md)


---

## Historical V4 Baseline Requirements (reference only; superseded where V4.1 refines them)

> **Historical UI exclusion:** Any older requirement below to create a React/TypeScript/Vite frontend, new browser pages, screens, or UI build/test pipeline is superseded by the user decision. These are historical notes, **not implementation tasks**. Preserve existing capabilities for later integration via document 35.

> This is preserved from the earlier planning draft for comparison. The current V4.1 design section, companion docs 30–34, the approved ADR register, and subsequent validated contracts take precedence on changes explicitly addressed in the V4.1 refinement. Historical descriptions of optional vector providers, open SQL fallback, and late Oracle tests are **not** new mandatory decisions.


The following material records relevant requirements from the previously agreed V4 blueprint. The sections above are the detailed module design and take precedence where they add stricter controls. Original V4 is a **proposed architecture**, not independently verified production source.

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

# 20. Security, Privacy and Governance

Security is a release blocker, not an optional optimization.

## 20.1 Trust boundaries

The application must treat the following as untrusted inputs:

- User questions.
- Uploaded content.
- Unapproved metadata descriptions.
- Model responses.
- Database text fields.
- Conversation history from external sources.

None of these inputs may override system permissions.

## 20.2 Mandatory controls

| Control | Requirement |
|---|---|
| Authentication | Approved identity provider and validated tokens |
| Authorization | Enforced for every request |
| Metadata filtering | Apply access controls before retrieval |
| Model isolation | Approved self-hosted inference |
| Database permissions | Least privilege, read-only business query identity |
| SQL policy | Independent allowlist and validation |
| Injection defense | Do not allow user/model instructions to alter security policy |
| Transport security | Approved TLS/internal networking |
| Secrets | Managed outside source code |
| Logging | Redacted and access controlled |
| Data retention | Defined session and telemetry retention rules |
| Audit | Record query and permission decisions safely |
| Rate limiting | Prevent resource abuse |
| Query limits | Protect Oracle from excessive workloads |

## 20.3 Model/data privacy

The system should not require sending business questions, schema metadata or customer results to an external inference API.

Any cloud service, embedding provider or monitoring system must be separately approved before receiving enterprise data.

Do not store customer records or sensitive sample values in vector indexes by default.

## 20.4 Security testing

Test attempts to:

- Access another user's sessions.
- Retrieve restricted fields.
- Bypass required filters.
- Generate DML/DDL.
- Use nested unsafe SQL.
- Access disallowed schemas.
- Force expensive queries.
- Inject malicious instructions through descriptions.
- Exfiltrate data through model/tool outputs.
- Circumvent per-user authorization with cached results.

Unauthorized execution must always fail closed.

---
