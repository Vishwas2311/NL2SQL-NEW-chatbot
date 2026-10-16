# 15 — Oracle Adapter, Secure Entity Lookup, Query Preflight and Resource Budgets

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Draft for review; no implementation or company production validation performed.  
**Document owner:** DBA + backend + security  
**Gate:** P0  
**Baseline reference:** V4 research/blueprint supplied on 2026-10-15.  
**Data policy:** Fictional examples only; actual company schema and customer data stay in approved office systems.

> **Core distinction:** this document specifies future behavior. It does not claim that these modules, controls, model benchmarks, or Oracle permissions are already deployed.

## Design specification

## Scope
This module receives opaque `ValidatedQuery` only, not SQL supplied by a web client or SLM. Query operations use a principal-scoped, least-privilege Oracle session; session/audit writes use a separate identity. Connection details and privileges are managed entirely within approved infrastructure. The adapter must support both native Oracle operation and synthetic database fixtures behind one protocol.

## Query execution pipeline
`ValidatedQuery -> identity/security-context verification -> concurrency admission -> preflight -> acquire pooled connection -> set DB-enforced session context (where applicable) -> execute binds -> stream/limit typed rows -> release connection -> return QueryExecutionResult`.

## Preflight specifics
- Verify allowed catalog/policy/compiler versions and query digest match the validator-produced capability.
- Reject expired request deadlines and missing principal context.
- Estimate complexity using deterministic join count, requested cardinality/row limit, approved table size class and/or DBA-approved Oracle plan mechanism. `EXPLAIN PLAN` is not inherently cost-free or always permitted; use only where approved, and do not pretend it guarantees runtime cost.
- Enforce statement timeout via supported Oracle driver/database mechanisms, concurrency semaphore, total response byte budget, scan limits where feasible and cancellation.
- Prevent dangerous implicit type conversions and unbounded `LIKE` scans where practical; enforce typed bind variables.

## Oracle driver policy
Use `python-oracledb` connection pool with configurable min/max, acquisition deadline, health checks, transaction/read-only behavior and cleanup. Confirm thin/thick driver choice against enterprise auth and Oracle release. Verify session identity reset after pool reuse so grants/tenant context never bleed between requests.

## Failure codes
`CONNECT_TIMEOUT`, `POOL_EXHAUSTED`, `PREFLIGHT_REJECTED`, `QUERY_TIMEOUT`, `QUERY_CANCELLED`, `ORA_DIALECT_ERROR`, `RESULT_LIMITED`, `DB_UNAVAILABLE`, `DB_PERMISSION_DENIED`. Do not return raw stack traces, full schema names or connection strings to users.

## Data contracts
`QueryExecutionResult` includes column metadata, typed rows/iterator, row count, truncated flag, execution duration, query_id, source snapshot/refresh timestamp when known, and safe error code. Separate the safe user-facing response from protected internal SQL and bind telemetry.

## Integration gates
Development SQLite adapter must implement the interface but Oracle production cannot be certified by SQLite passing. Run an office-only Oracle fixture suite for DATE/TIMESTAMP, NUMBER precision, CLOB, ROWNUM/FETCH, null semantics, DB policy and pooled-session context isolation. No production write privileges for query account.



## V4.1 early Oracle compatibility and preflight protocol
**Start dialect qualification in parallel with synthetic compiler work as soon as a sanctioned Oracle test instance is available, not as a last-phase surprise.** Verify driver Thin/Thick compatibility, Oracle version, identifiers, bind types, date/timezone behavior, decimal precision, NULL, `FETCH FIRST`, analytics, CTE and optimizer behavior for approved semantic views.
Preflight is a separate resource gate after SQL validation. It may use the approved Oracle explain-plan/cost strategy when available, but estimates are advisory and must combine with hard session/statement limits, read-only permissions, DB-side resource controls, cancellation and result limits. Never describe EXPLAIN PLAN as a complete security or query-time guarantee. The query executor must reassert principal, grants, session context and pinned catalog version. See [33](./33_ORACLE_EARLY_COMPATIBILITY_AND_PREFLIGHT.md).

---

## Deliverables / artifacts to review

Oracle adapter protocol, preflight policy, pool configuration, bind contract, error taxonomy, resource-protection test plan

## Acceptance tests and exit criteria

Accepted query executes once, slow query cancels, pool context isolated, unauthorized query blocked even if app misbehaves

## Open decisions and evidence required

Oracle version, query resource profiles, VPD policy, driver thin/thick, DB plan privilege, connection budget?

## Related documents

[08](./08_ENTITY_AND_VALUE_RESOLUTION.md), [10](./10_QUERY_PLAN_DSL_AND_VALIDATION.md), [14](./14_SQL_VALIDATION_POLICY_AND_SECURITY.md), [20](./20_CACHING_LATENCY_AND_RESOURCE_BUDGETS.md), [21](./21_SECURITY_PRIVACY_THREAT_MODEL.md), [22](./22_PRIVATE_DEPLOYMENT_INFRA_AND_FULCRUM.md)


---

## Preflight levels and degradations
Preflight should have **static controls** that need no Oracle round trip (estimated joins, bounded rows, table size class, hard denied functions), **database-assisted** controls if DBA grants suitable plan inspection, and **runtime** controls (timeout/concurrency/CPU quota). If plan estimation is unavailable, use conservative static budgets, not an unverified “zero cost” assumption. Always preserve Oracle authorization as final enforcement.

### State machine
`admitted -> policy_verified -> preflight_ok -> pool_acquired -> executing -> {succeeded | limited | timed_out | cancelled | db_error} -> released`. Connection release and session context cleanup run on every path including cancellation/exceptions. Never replay a statement automatically after a timeout unless side-effect-free semantics and idempotency are positively established.

### Oracle integration negative cases
Pooled connection retains a previous user's VPD/session context; database must reset it. DATE-vs-TIMESTAMP boundary shifts daily count. Number returned as floating point loses monetary cents; use Decimal. A query's `FETCH FIRST` clause is unsupported on target version; gate SQL dialect. Expensive query with no plan access must be limited by policy. User-set bind string containing quotes must remain a bound value.

---

## Historical V4 Baseline Requirements (reference only; superseded where V4.1 refines them)

> **Historical UI exclusion:** Any older requirement below to create a React/TypeScript/Vite frontend, new browser pages, screens, or UI build/test pipeline is superseded by the user decision. These are historical notes, **not implementation tasks**. Preserve existing capabilities for later integration via document 35.

> This is preserved from the earlier planning draft for comparison. The current V4.1 design section, companion docs 30–34, the approved ADR register, and subsequent validated contracts take precedence on changes explicitly addressed in the V4.1 refinement. Historical descriptions of optional vector providers, open SQL fallback, and late Oracle tests are **not** new mandatory decisions.


The following material records relevant requirements from the previously agreed V4 blueprint. The sections above are the detailed module design and take precedence where they add stricter controls. Original V4 is a **proposed architecture**, not independently verified production source.

# 14. Oracle Database Integration

## 14.1 Database adapter

Use a clean database interface.

Suggested operations:

- `health_check()`
- `execute_select()`
- `get_allowed_schema_metadata()`
- `cancel_query()`
- `close()`

The interface should not expose arbitrary database execution to the SLM.

## 14.2 Oracle driver

Use `python-oracledb` with approved connection configuration.

Evaluate thin versus thick mode according to Oracle version, authentication requirements and organizational standards.

## 14.3 Connection management

Implement:

- Connection pooling.
- Maximum concurrent connections.
- Connection acquisition timeout.
- Idle connection cleanup.
- Error recovery.
- Pool health checks.
- Statement cancellation where supported.
- Clean application shutdown.

## 14.4 Database identity separation

Use separate access responsibilities:

**Query identity**

- Read-only access to approved objects.
- Database-enforced row and column controls.
- Query resource limits.

**Session/audit identity**

- Limited permissions to write chatbot-owned session and audit data.
- No unrestricted business-data modification permissions.

Do not use a broad application account with write access to the business database.

## 14.5 Bind parameters

All user-provided filter values must be bound as parameters.

Dynamic table and column identifiers must come from approved catalog allowlists.

## 14.6 Oracle-specific testing

The compiler and validator must be tested for:

- Oracle-compatible date operations.
- Timestamp and timezone behavior.
- NULL handling.
- Pagination.
- Numeric precision.
- String comparisons.
- CLOB handling.
- Aggregate expressions.
- Identifier case sensitivity.
- Analytic functions.
- Version-dependent syntax.

SQLite execution is useful for development but cannot prove Oracle SQL compatibility.

## 14.7 Query results

The executor should return a typed result containing:

- Column names and types.
- Rows.
- Row count or truncation indicator.
- Execution status.
- Elapsed execution time.
- Query reference ID.
- Safe warnings.

Do not return raw Oracle exception details directly to users.

---
