# 07 — Verified Join Graph, Aggregation Grain and Temporal Correctness

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Draft for review; no implementation or company production validation performed.  
**Document owner:** DBA + data engineering  
**Gate:** P0  
**Baseline reference:** V4 research/blueprint supplied on 2026-10-15.  
**Data policy:** Fictional examples only; actual company schema and customer data stay in approved office systems.

> **Core distinction:** this document specifies future behavior. It does not claim that these modules, controls, model benchmarks, or Oracle permissions are already deployed.

## Design specification

## Topology
Use a versioned in-process graph of *physical* allowlisted tables/views. Nodes carry table grain and key classifications. Edges carry explicit join expressions composed from approved column IDs, not SQL snippets generated from text. Store separate logical relationships for business semantics; those cannot be automatically promoted to executable join edges.

## JoinPathResolver API
`resolve(metric_ids, dimension_ids, filter_ids, authz_scope, as_of, catalog) -> JoinPlan | Ambiguity | Unsupported`. Output includes ordered tables, complete key-pair predicates, chosen join types, required filters, cardinalities, preaggregation obligations and provenance. Graph shortest path alone is insufficient: there may be several semantically different relationships with identical hop count.

## Join selection rules
Require certified edge status, compatible domains, current catalog, valid composite keys and nonconflicting time constraints. No relationship is established merely because two fields share a name. If alternative paths affect meaning or multiplicity, require explicit metric preference or clarify. Detect cycles and reject unbounded traversal.

## Fan-out defense
Suppose each customer has 3 orders and 4 payments; naively joining both facts may create 12 intermediate rows. When a measure is at order grain and payments are at payment grain, the query engine must preaggregate appropriately or refuse the query. Define additive/semi-additive/non-additive behavior for each measure; prevent SUM over repeated fact rows. Keep grain proof and join evidence in the compilation manifest.

## Temporal semantics
Support snapshot-date versus event-date, effective start/end, inclusive/exclusive boundaries, late data, timezone, reporting calendar, changing customer status and as-of entity attributes. A historical query must not apply today’s `is_current` flag unless the certified rule explicitly instructs it. Use consistent half-open timestamp ranges where appropriate and check Oracle DATE/TIMESTAMP behavior separately.

## Required negative cases
One missing key of a composite join; incorrect many-to-many path; two candidate relationships; cross-domain prohibited path; orphaned metadata edge; current-state filter in an as-of query; one-to-many fan-out; off-by-one period. Each must fail safely or generate a semantically verified preaggregation.



## V4.1 semantic view and join-proof contract
A certified semantic view names a root/grain, allowed metric and dimension IDs, and a physical relationship dependency subgraph. `JoinResolver.resolve(view_id, selected_fields, as_of, principal, snapshot)` must return explicit composite join predicates, all mandatory time/policy filters, cardinality evidence, and either a safe aggregation-order plan or an `UNSAFE_FANOUT` rejection. Graph traversal is **not** a license to concatenate every shortest path: shortest topological path may be semantically invalid.
**Default implementation:** NetworkX in-memory `MultiDiGraph` or minimal equivalent adjacency structure, compiled from versioned approved metadata at startup. Choose NetworkX as the first implementation for tests/debuggability; optimize to adjacency lists only if measured load/query overhead requires it. No Neo4j server or Graphify import is a prerequisite. Edges missing physical evidence remain candidate-only.
Golden joins must cover duplicate totals (two independent many-side facts), composite keys, alternative paths, historical as-of joins, NULL key behavior, fan-out, nested dimensions and policy-restricted bridge tables. Document which approved semantic views eliminate repeated join construction. See [31](./31_GOVERNED_SEMANTIC_VIEWS_AND_COVERAGE.md).

---

## Deliverables / artifacts to review

Graph node/edge types, JoinPlan contract, grain inference proof, temporal policy fixtures

## Acceptance tests and exit criteria

All required joins verified, composite keys complete, aggregation and as-of golden results correct

## Open decisions and evidence required

Which joins are certified logical versus declared DB constraints? Are there time-valid relation keys?

## Related documents

[04](./04_SEMANTIC_CATALOG_AND_GOVERNANCE.md), [05](./05_METADATA_INGESTION_AND_RECONCILIATION.md), [10](./10_QUERY_PLAN_DSL_AND_VALIDATION.md), [12](./12_DETERMINISTIC_SQL_COMPILER_AND_TEMPLATES.md), [14](./14_SQL_VALIDATION_POLICY_AND_SECURITY.md)


---

## Relationship representation and proof
```yaml
relationship_id: orders_to_customers
source_table_id: orders
source_key_ids: [customer_id]
target_table_id: customers
target_key_ids: [customer_id]
cardinality: many_to_one
join_types_allowed: [inner, left]
temporal_policy_id: none
verified_status: certified
```
This is fictional. A `JoinPlan` should also explain: start grain, target grain, expected duplication, permitted preaggregation, active temporal constraints, selected alternative-path justification and immutable edge IDs. A path's validity may depend on metric, reporting period and user role; store or derive these conditions.

### Fan-out proof test
Synthetic fixture: one customer with 3 orders and 4 payments. Naive join should generate 12 combinations. An `orders_total` metric over order grain must not be summed after the naive join. Our safe compiler either preaggregates orders and payments separately at customer grain, uses a certified subquery structure or denies unsupported combined metrics. Golden expected totals must be compared to independently computed synthetic facts, not to model-generated SQL text.

### Temporal proof test
A customer is labeled low-risk until June 30 and high-risk from July 1; an as-of June 15 query must select low-risk, an as-of July 10 query high-risk. Effective intervals and timezone conversions must be documented; no implicit `current_flag=1` for historical requests. Overlapping effective rows are a catalog/data quality failure until policy chooses one record deterministically.

---

## Join resolver input/output walkthrough
When asked for `net_sales` by `region`, the metric registry first supplies the certified base grain (order line or order, as defined by the owner). The dimension registry supplies the physical source of region. The resolver enumerates **approved** paths, not arbitrary graph edges, then checks all key pairs and whether the path duplicates the metric's base grain. The plan explicitly records whether distinct selection, preaggregation or a different certified source view is required. If no proof is possible, return `JOIN_NOT_VERIFIED` and do not generate SQL.

### Edge-level tests to implement
| Test ID | Input | Expected behavior |
|---|---|---|
| G-01 | Two tables with identical `id` names, no edge | No join offered |
| G-02 | Composite join missing second key | Reject invalid edge |
| G-03 | One-to-many join with SUM | Preaggregate or deny |
| G-04 | Two approved paths with different meaning | Request clarification |
| G-05 | Edge approved only for another domain | Deny path |
| G-06 | Prior catalog version edge after publication | Reject stale plan |
| G-07 | Historical dimension with as-of date | Apply certified effective interval |
| G-08 | User restricted from intermediate join table | Do not traverse into restricted table |

### Complexity
For tens of tables, bounded BFS/shortest-path enumeration in Python is inexpensive. However, shortest path is never the entire selection criterion: semantic compatibility, cardinality, time rules, authorization and metric-specific preferences dominate hop count. Graph traversal must have a maximum path length/expansion budget to avoid unbounded graph exploration.

---

## Historical V4 Baseline Requirements (reference only; superseded where V4.1 refines them)

> **Historical UI exclusion:** Any older requirement below to create a React/TypeScript/Vite frontend, new browser pages, screens, or UI build/test pipeline is superseded by the user decision. These are historical notes, **not implementation tasks**. Preserve existing capabilities for later integration via document 35.

> This is preserved from the earlier planning draft for comparison. The current V4.1 design section, companion docs 30–34, the approved ADR register, and subsequent validated contracts take precedence on changes explicitly addressed in the V4.1 refinement. Historical descriptions of optional vector providers, open SQL fallback, and late Oracle tests are **not** new mandatory decisions.


The following material records relevant requirements from the previously agreed V4 blueprint. The sections above are the detailed module design and take precedence where they add stricter controls. Original V4 is a **proposed architecture**, not independently verified production source.

# 7. Relationship Graph and Join Resolution

## 7.1 Purpose

The relationship graph determines how physical database objects may be joined.

It is not primarily a visualization tool.

## 7.2 Recommended implementation

Use a Python in-memory adjacency graph.

A small custom implementation or NetworkX is sufficient for the initial version.

The graph is built from versioned, approved relationship metadata.

Graph nodes may represent tables or approved database views.

Graph edges contain validated join information.

## 7.3 Required edge properties

Every SQL join relationship must contain:

- Source table.
- Target table.
- Source columns.
- Target columns.
- Cardinality.
- Allowed join types.
- Allowed domain context.
- Required predicates.
- Temporal conditions.
- Verification status.
- Provenance.

## 7.4 Join resolution algorithm

Given selected tables:

1. Verify table authorization.
2. Identify available approved join paths.
3. Reject forbidden domain crossings.
4. Prefer paths with stronger verification.
5. Detect multiple conflicting paths.
6. Detect one-to-many fan-out risks.
7. Check required grain.
8. Apply effective-date conditions.
9. Return a complete join specification.

If multiple paths produce different business interpretations, ask for clarification rather than choosing arbitrarily.

## 7.5 Aggregation grain

This is one of the most important correctness controls.

Suppose a customer has three orders and four payments.

A naive join may create twelve intermediate rows, resulting in incorrect totals.

The query planner must recognize when facts need aggregation before joining.

Our compiler should support:

- Pre-aggregation.
- Distinct counts where defined.
- Appropriate grouping keys.
- Relationship-aware joins.
- Prevention of unsupported many-to-many aggregation.
- Historical record selection.

These rules should be tested independently of Gemma.

---
