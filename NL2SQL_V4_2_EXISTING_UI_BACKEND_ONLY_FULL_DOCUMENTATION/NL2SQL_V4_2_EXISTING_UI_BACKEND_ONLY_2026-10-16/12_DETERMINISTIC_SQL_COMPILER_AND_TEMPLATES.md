# 12 — Semantic SQL Compiler, Templates and Oracle Dialect

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Draft for review; no implementation or company production validation performed.  
**Document owner:** Backend compiler team + DBA  
**Gate:** P0  
**Baseline reference:** V4 research/blueprint supplied on 2026-10-15.  
**Data policy:** Fictional examples only; actual company schema and customer data stay in approved office systems.

> **Core distinction:** this document specifies future behavior. It does not claim that these modules, controls, model benchmarks, or Oracle permissions are already deployed.

## Design specification

## Compiler responsibility
The compiler receives only `ValidatedPlan` and a published catalog. It constructs relational operations deterministically, selects approved source mappings, applies mandatory filters, performs grain-safe joins, emits parameterized target-dialect SQL and returns an auditable compilation manifest. It cannot infer new business metric definitions.

## Compilation stages
`ValidatedPlan -> metric expression graph -> required physical sources -> approved join plan -> temporal/row filters -> pre-aggregation where needed -> typed relational IR -> Oracle dialect rendering -> SQL + binds + manifest`.

## Initial supported relational grammar
Projection, typed `WHERE` (AND/OR + compare + IN with bounded arity), safe join, GROUP BY, HAVING, SUM/COUNT/AVG/MIN/MAX, ORDER BY, top-N, ISO reporting periods, simple CTE, preaggregation and permitted NULL operations. Later consider CASE, analytic windows, percentiles, distinct-subset count and nested comparisons. Each feature should have explicit capability flag and golden fixture.

## CompiledQuery envelope
`sql`, `binds`, `expected_output_columns`, `metric_ids`, `column_ids`, `join_edge_ids`, `required_policies`, `source_catalog_digest`, `compiler_version`, `estimated_grain`, `timestamp_rule_ids`. Internal SQL may be stored only under audited access, not public response by default.

## Templates
Store certified query-plan templates with slot specifications (metric, period, allowed enum/entity filters), not raw string-substitution snippets. Bind every value. Use strict intent matching; the fast path should abstain on ambiguous near matches. Templates must be versioned, tested and approved like code.

## Dialect safety
Construct Oracle-compatible bind names, fetch/row limits, identifiers, date and interval logic, NUMBER/DECIMAL arithmetic, DATE/TIMESTAMP precision and NULL semantics. SQLite adapter validates business logic in development; only an approved Oracle integration suite can prove Oracle execution. SQLGlot may support AST construction/inspection but is not sufficient alone for security, semantics or Oracle execution guarantees.

## Fallback classification
Compiler returns either `CompiledQuery`, `UnsupportedFeature(feature_id)` or `InvalidSemanticPlan(reason)`. Only `UnsupportedFeature` for an allowlisted operation may trigger restricted SLM SQL fallback. Missing metric, unknown join, bad grant, ambiguous date and invalid data grain **never** invoke fallback.



## V4.1 compiler support for governed semantic views
Compiler input is `ValidatedPlan` pinned to a certified catalog snapshot. Stage order: resolve the requested `semantic_view_id` or select an approved matching view → expand its certified metric/dimension dependencies → resolve grain and effective time role → use approved physical source/view mapping → apply pre-aggregation/window/joins as supported → inject mandatory filters and auth scope through policy-safe bind parameters → produce Oracle dialect AST/SQL + `CompiledQueryProof`. A logical view compiles into source queries/CTEs; an approved physical Oracle view compiles into references to that allowed object. Neither permits arbitrary caller-supplied SQL.
**Compiler feature boundary:** P0 selects, typed predicates, approved joins, filters, group by, additive aggregates, ranking/limits, standard reporting dates; P1 approved semi-additive snapshots, pre-aggregation, carefully tested windows and multiple time roles; P2 exotic analytic functions. Non-covered operations return structured `UNSUPPORTED_COMPILER_OPERATOR`, never a partially correct SQL draft. Template matches always retain the plan proof and pass normal validation.
**Proof fields:** semantic view/version, metric versions, join-path IDs, grain proof, required filters, policy digest, Oracle dialect target, parameter types, output types and expected data-as-of role. Oracle-specific syntax must be tested against the approved Oracle version (see 33).

---

## Deliverables / artifacts to review

Relational intermediate representation, compiler stage APIs, Oracle renderer, approved template registry

## Acceptance tests and exit criteria

Golden SQL results across join/grain/time/null/bind scenarios; unsupported feature flagged cleanly; no string injection

## Open decisions and evidence required

Which Oracle version and SQL functions supported? Who approves query templates and default row limits?

## Related documents

[04](./04_SEMANTIC_CATALOG_AND_GOVERNANCE.md), [07](./07_JOIN_GRAPH_GRAIN_AND_TEMPORAL_RULES.md), [10](./10_QUERY_PLAN_DSL_AND_VALIDATION.md), [14](./14_SQL_VALIDATION_POLICY_AND_SECURITY.md), [15](./15_ORACLE_ADAPTER_PREFLIGHT_AND_RESOURCES.md)


---

## Deterministic compilation correctness contract
The compiler must never string-concatenate unchecked filter values or guess primary keys from column names. Define a relational IR with typed nodes `ScanApprovedView`, `Filter`, `JoinCertified`, `Aggregate`, `Project`, `Sort`, `Limit`, `AsOf`, `Preaggregate`. Every node carries expected schema, grain and semantic provenance. AST rendering receives only IR nodes and driver bind values.

### Compiler fixture cases
| Feature | Positive | Negative |
|---|---|---|
| Aggregation | Certified net_sales SUM on order grain | SUM of semi-additive snapshot across dates |
| Join | Verified customer-to-order key | Implicit join by same-named but unapproved ID |
| Time | Effective-date as-of filter | Current row selected for historical date |
| Limit | Bounded Top-N after sort | Unbounded model-selected limit |
| SQL filter | Bound typed customer ID | Raw SQL expression in filter value |

**Compiler output proof:** For a question on regional sales, the manifest must include metric ID, calendar definition, certified edge IDs, preaggregation decision, exact parameter list and expected output units. If this proof cannot be produced, compilation must not silently succeed. Runtime SQL AST validation should compare actual referenced sources to this manifest.

---

## Historical V4 Baseline Requirements (reference only; superseded where V4.1 refines them)

> **Historical UI exclusion:** Any older requirement below to create a React/TypeScript/Vite frontend, new browser pages, screens, or UI build/test pipeline is superseded by the user decision. These are historical notes, **not implementation tasks**. Preserve existing capabilities for later integration via document 35.

> This is preserved from the earlier planning draft for comparison. The current V4.1 design section, companion docs 30–34, the approved ADR register, and subsequent validated contracts take precedence on changes explicitly addressed in the V4.1 refinement. Historical descriptions of optional vector providers, open SQL fallback, and late Oracle tests are **not** new mandatory decisions.


The following material records relevant requirements from the previously agreed V4 blueprint. The sections above are the detailed module design and take precedence where they add stricter controls. Original V4 is a **proposed architecture**, not independently verified production source.

# 11. Deterministic SQL Compiler

## 11.1 Purpose

This component converts validated query plans into SQL using approved definitions.

It should not require an LLM call.

## 11.2 Recommended implementation

Use a purpose-built semantic query builder with a typed intermediate representation.

Use a reliable SQL AST/building library where appropriate and test Oracle-specific syntax explicitly.

SQLGlot can assist with parsing and AST operations, but it is not by itself a complete Oracle compiler or security validator.

SQLAlchemy Core may be evaluated for SQL construction if its Oracle dialect behavior meets our needs.

The important requirement is controlled, parameterized SQL generation.

## 11.3 Compiler features for version one

| SQL capability | Priority |
|---|---|
| SELECT columns | P0 |
| WHERE conditions | P0 |
| Bind parameters | P0 |
| AND / OR expressions | P0 |
| ORDER BY | P0 |
| Row limits | P0 |
| COUNT, SUM, AVG, MIN, MAX | P0 |
| GROUP BY | P0 |
| HAVING | P0 |
| Approved table joins | P0 |
| DATE and reporting-period filters | P0 |
| Approved metric calculations | P0 |
| Historical effective-date queries | P0 |
| Common table expressions | P1 |
| Pre-aggregation | P1 |
| Window functions | P1 |
| Complex conditional expressions | P1 |
| Advanced analytic SQL | P2 |
| Specialized Oracle functions | P2 |

This feature set should expand according to measured business requirements.

## 11.4 Compiler workflow

Validated QueryPlan → resolve approved metrics → resolve dimensions → determine source objects → find join paths → apply mandatory filters → apply date rules → construct SQL expression tree → render Oracle SQL → produce bind parameters.

## 11.5 Compilation result

The compiler must return:

- SQL string.
- Bind parameters.
- Referenced metadata IDs.
- Applied metric definitions.
- Selected join path IDs.
- Expected output columns and types.
- Catalog version.
- Compilation diagnostics.

The validator should have access to this information independently of the SQL text.

## 11.6 Prepared templates

For high-frequency queries, store parameterized templates.

Templates must have:

- Version.
- Approved schema dependencies.
- Accepted parameters.
- User permission requirements.
- Test coverage.
- Approval and rollback metadata.

Template matching must be strict enough to avoid returning the wrong answer to a similar question.

---
