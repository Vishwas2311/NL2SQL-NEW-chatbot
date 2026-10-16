# 10 — Typed Query DSL, Pydantic Models and Plan Validation

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Draft for review; no implementation or company production validation performed.  
**Document owner:** Backend + data engineering  
**Gate:** P0  
**Baseline reference:** V4 research/blueprint supplied on 2026-10-15.  
**Data policy:** Fictional examples only; actual company schema and customer data stay in approved office systems.

> **Core distinction:** this document specifies future behavior. It does not claim that these modules, controls, model benchmarks, or Oracle permissions are already deployed.

## Design specification

## Type contract
The SLM emits a declarative plan referencing certified IDs. It does not decide Oracle table aliases, raw join SQL, auth context, datasource endpoints or row policy. A source-free normal plan has `intent`, metric/entity IDs, dimensions, typed filters (boolean nesting), grain, time period, sort, limit, query mode and catalog version. The server attaches principal and permissions; the model cannot override them.

## Minimal fictional example
```json
{
 "schema_version":"1.0", "intent":"ranking", "metric_ids":["net_sales"],
 "dimension_ids":["region"],
 "filters":{"op":"AND","children":[{"field_id":"order_year","op":"EQ","value":2025}]},
 "sort":[{"id":"net_sales","direction":"DESC"}], "limit":10,
 "catalog_version":"test-v1"
}
```

## Validation order
1. Parse constrained JSON into typed `QueryPlan`. Reject extra unknown keys.
2. Verify same published catalog version and authenticated tenant/user access.
3. Resolve each metric/dimension/filter by certified stable IDs.
4. Check operator/type compatibility; coerce only explicitly supported values, never SQL fragments.
5. Resolve reporting date and timezone semantics.
6. Verify metric-dimension grain, required filters, join-path existence and domain restrictions.
7. Apply maximum row/complexity policies and reject arbitrary negative or enormous limits.
8. Produce immutable `ValidatedPlan` with a proof manifest (catalog hash, IDs, policy decisions, semantic rules).

## Outcome taxonomy
`VALID`, `CLARIFICATION_REQUIRED`, `UNSUPPORTED`, `METRIC_UNCERTIFIED`, `INVALID_VALUE`, `INVALID_JOIN`, `GRAIN_CONFLICT`, `PERMISSION_DENIED`, `CATALOG_STALE`, `LIMIT_EXCEEDED`. The user-visible error is intentionally coarser than internal diagnostic detail.

## Extension/versioning
Use additive plan versions; include a version adapter where possible. Compiler declares supported AST/DSL operators. Unsupported DSL cannot be smuggled through raw SQL expression strings; route through feature-gated fallback only after semantic validation.



## V4.1 typed query DSL enhancements
Add optional `semantic_view_id` and `view_version` **only when selected from the certified catalog**, `MetricRef` and `DimensionRef` by stable ID, typed `DateRole`/`AsOfDate`/`FiscalPeriod`, `AggregatePolicy`, `ValueResolutionRef` and `SourceProvenanceRef`. The SLM cannot supply DB owner/table names, SQL fragments, entitlements, free-form metric formulas or connection URLs.
Validation includes view-field compatibility, mixed-grain detection, semi-additive measure grouping, date-role disambiguation, entitlement, dependent physical mapping completeness, and query operation support. A compiler capability miss is `UNSUPPORTED_COMPILER_OPERATOR`, distinct from `MISSING_SEMANTIC_PROOF` or `UNAUTHORIZED`, and only the former may route to the guarded fallback. Contract version change requires migration tests and JSON Schema version pinning. See [31](./31_GOVERNED_SEMANTIC_VIEWS_AND_COVERAGE.md) and [34](./34_TRACEABILITY_DECISIONS_AND_FINAL_REVIEW.md).

---

## Deliverables / artifacts to review

QueryPlan JSON schema, Pydantic classes contract, validator decisions, proof manifest and migration policy

## Acceptance tests and exit criteria

No raw SQL identifiers/clauses from model; incompatible metrics refused; typed date/number filters and nested AND/OR supported

## Open decisions and evidence required

Which analytic operators are essential at launch? Should money use Decimal and explicit currency?

## Related documents

[04](./04_SEMANTIC_CATALOG_AND_GOVERNANCE.md), [07](./07_JOIN_GRAPH_GRAIN_AND_TEMPORAL_RULES.md), [08](./08_ENTITY_AND_VALUE_RESOLUTION.md), [09](./09_ROUTING_CONFIDENCE_AND_EXECUTION_PATHS.md), [11](./11_LOCAL_SLM_MODEL_CONTEXT_AND_RUNTIME.md), [12](./12_DETERMINISTIC_SQL_COMPILER_AND_TEMPLATES.md), [14](./14_SQL_VALIDATION_POLICY_AND_SECURITY.md)


---

## DSL invariants and versioned schema rules
- `metric_ids`, `dimension_ids`, `entity_ids` and `field_ids` must map to certified stable IDs. The SLM may select from enums, but only server code resolves these to Oracle physical names.
- Filter values are typed `string | decimal | integer | date | timestamp | boolean | list[...]`, not a raw SQL expression. Currency arithmetic uses precise decimal rules and explicit unit/currency.
- Time expressions are typed: `absolute_range`, `previous_quarter`, `as_of`, `fiscal_year`, `rolling_window`. The catalog resolves fiscal month boundaries and time zones. Values must not come from ambiguous model text when semantics are missing.
- The DSL permits nested conditions with maximum depth and cardinality; only allowed operators for each field type. Define `IN` maximum values, regex policy, sort references, pagination and authorized default limits.

### Plan manifest sample (synthetic)
```json
{
  "catalog_version":"demo-v1",
  "metric_ids":["net_sales"],
  "approved_relationship_ids":["orders_to_customer","customer_to_region"],
  "grain":["region"],
  "period":{"type":"year","value":2025},
  "mandatory_filter_ids":["completed_only"],
  "policy_id":"analyst_read_v1"
}
```
This proof manifest is constructed by the trusted plan validator, **not by the SLM**, and accompanies compilation and later AST checks.

### Validation test matrix
Unknown field ID → `UNSUPPORTED`; mismatched text/date operator → `INVALID_FILTER`; multiple metric definitions → `CLARIFICATION_REQUIRED`; unauthorized dimension → `DENIED`; catalog mismatch → `CATALOG_STALE`; missing required date filter → `INVALID_SEMANTIC_PLAN`; unbounded limit → `LIMIT_EXCEEDED`. Errors should not leak restricted table names to browser.

---

## Exact query-plan JSON design decisions
We must define `FilterValue` with tagged type (`decimal`,`integer`,`string`,`date`,`timestamp`,`boolean`,`string_list`), never Python-eval expressions. Define `TimeRange` with timezone, inclusive/exclusive boundaries and reporting-calendar ID. Define `Aggregation` as a certified metric ID, not `SUM(any_user_column)` unless an explicit policy allows ad-hoc calculation. Define `Comparison` as a typed pair of periods, not an arbitrary SQL `CASE` string.

### Server-owned fields
`principal_id`, `tenant_id`, `authorization_scope`, `database_connection`, `timeout`, `allowed_table_set`, `catalog_signature`, `requested_at` are supplied by trusted backend logic. If Gemma returns any of these in JSON, reject unknown fields. The model must not be able to increase limits or disable validation in a `QueryPlan`.

### Compiled plan request object
```json
{
 "intent":"ranking",
 "metric_ids":["net_sales"],
 "dimensions":["region"],
 "filters":[{"field_id":"order_year","op":"eq","value_type":"integer","value":2025}],
 "sort":[{"field_id":"net_sales","direction":"desc"}],
 "limit":10
}
```
This remains a **draft** until independently validated. Validation materializes the authoritative metric formula, necessary joins, mandatory filters and catalog/policy provenance into an immutable proof. Later model calls cannot edit that proof.

### DSL migration tests
A v1 parser cannot silently accept a v2-only operation. Unknown fields/versions result in typed upgrade-required or unsupported statuses. A null optional filter means “absent”; it must not accidentally translate into `= NULL`. Empty `IN` lists must have defined semantics. Decimal and currency types must not implicitly become float in JSON round trips. All operator combinations require table-driven unit tests.

---

## Historical V4 Baseline Requirements (reference only; superseded where V4.1 refines them)

> **Historical UI exclusion:** Any older requirement below to create a React/TypeScript/Vite frontend, new browser pages, screens, or UI build/test pipeline is superseded by the user decision. These are historical notes, **not implementation tasks**. Preserve existing capabilities for later integration via document 35.

> This is preserved from the earlier planning draft for comparison. The current V4.1 design section, companion docs 30–34, the approved ADR register, and subsequent validated contracts take precedence on changes explicitly addressed in the V4.1 refinement. Historical descriptions of optional vector providers, open SQL fallback, and late Oracle tests are **not** new mandatory decisions.


The following material records relevant requirements from the previously agreed V4 blueprint. The sections above are the detailed module design and take precedence where they add stricter controls. Original V4 is a **proposed architecture**, not independently verified production source.

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
