# 04 — Certified Semantic Catalog and Metric Governance

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Draft for review; no implementation or company production validation performed.  
**Document owner:** Domain owners + data engineering  
**Gate:** P0  
**Baseline reference:** V4 research/blueprint supplied on 2026-10-15.  
**Data policy:** Fictional examples only; actual company schema and customer data stay in approved office systems.

> **Core distinction:** this document specifies future behavior. It does not claim that these modules, controls, model benchmarks, or Oracle permissions are already deployed.

## Design specification

## Authority model
One versioned canonical catalog contains typed records for domains, business entities, dimensions, metrics, physical tables/views, columns, synonyms, joins, sensitivity, time rules and approvals. Business owners certify semantics; DBAs certify physical objects; security approves access policy. Unverified Graphify or spreadsheet records are *candidates*, never executable authority.

## Required metadata contracts
| Type | Core required fields | Validation |
|---|---|---|
| `Metric` | id, business definition, expression DSL, grain, unit, default filter, time dimension, allowed dimensions | owner approval; formula type checking; aggregate compatibility |
| `Entity` | id, business aliases, base view, natural/business keys, sensitivity | documented key and entity-resolution scope |
| `Dimension` | id, column or derived expression, type, permitted filters, valid metrics | source exists and entitlement passed |
| `Relation` | left/right objects, column pairs, cardinality, join type, pre-agg rules, temporal predicate, evidence | verified and policy-approved |
| `Table` | ID, owner, name, grain, allowlisted columns, class, time attributes | Oracle data dictionary reconciliation |
| `CatalogSnapshot` | ID/version, checksums, approval, effective time, index version, previous version | atomic publication + rollback |

## Domain semantics checklist
For each governed metric specify the numerator/denominator if any, row eligibility, exclusions, period boundaries, status filtering, currency/unit conversion, zero and NULL behavior, time validity, rounding, aggregate type (additive, semi-additive, non-additive), aggregation grain and compatible dimensions. A field label like “EXPOSURE” is insufficient to define an approved total.

## Example fictional metric
```yaml
id: net_sales
status: certified
owner_role: finance_steward
base_entity: orders
grain: [order_id]
expression: amount_minus_discount
unit: USD
time_dimension: fulfilled_at
mandatory_filters: [state_is_completed]
allowed_dimensions: [region, month]
relationships: [orders_to_customer, customer_to_region]
null_policy: discount_as_zero
```
This is illustrative. The DSL expression must reference certified operators/IDs and be compiled, never evaluated as arbitrary Python or raw SQL from the user.

## Trust and publication workflow
`draft -> technical_verified -> business_certified -> security_approved -> published -> deprecated`. Publication requires no invalid foreign references, verified physical mappings, compile-test pass and golden-case results. Restrict edits to stewards; persist change author, diff, timestamps and reviewer signatures. Maintain one active snapshot per environment and rollback on validation failure.

## Handling conflicts
When a metric points to a field absent from Oracle, mark invalid and block dependent queries. When two metrics share the same display name, require a scoped domain or clarification. When catalog and schema disagree on data type, quarantine affected objects. When historical formula changes exist, resolve definition by as-of period and report the effective version.



## V4.1 certified semantic-view extension
Add `SemanticViewDefinition` to the canonical catalog, **without creating a second authority**. Required fields: immutable view ID/version, domain, business entity, native grain, output field IDs/types, allowed metrics/dimensions, source physical objects or approved Oracle view reference, required joins, mandatory predicates, time roles/as-of semantics, source lineage, policy classification, effective period, approval status and certification evidence. Version view definitions along with the metric catalog and derived indexes.
A view must **not** flatten two one-to-many fact sources by default. Use certified pre-aggregation and grain-preserving constructs. Non-additive and semi-additive measures require approved aggregation semantics; a cross-domain metric must have reviewed lineage. Different business meanings with similar labels require separate IDs.
Publishing blocks view activation on unresolved source mapping, unverified join, fan-out counterexample, temporal rule gap, inconsistent entitlement, or missing independent golden answers. Physical and logical views have the same governed interface but different deployment requirements; only the DBA can approve Oracle DDL. See [31](./31_GOVERNED_SEMANTIC_VIEWS_AND_COVERAGE.md).

---

## Deliverables / artifacts to review

Versioned catalog schema, governance workflow, metric approval checklist, synthetic catalog fixtures

## Acceptance tests and exit criteria

Undefined metric denied; semantic conflict rejected; version publication atomic; metric/grain/date golden checks

## Open decisions and evidence required

Who are metric approvers? Are business definitions available? What are approved fiscal calendars and sensitivity classes?

## Related documents

[03](./03_SYSTEM_ARCHITECTURE_AND_RUNTIME.md), [05](./05_METADATA_INGESTION_AND_RECONCILIATION.md), [07](./07_JOIN_GRAPH_GRAIN_AND_TEMPORAL_RULES.md), [08](./08_ENTITY_AND_VALUE_RESOLUTION.md), [10](./10_QUERY_PLAN_DSL_AND_VALIDATION.md), [12](./12_DETERMINISTIC_SQL_COMPILER_AND_TEMPLATES.md), [14](./14_SQL_VALIDATION_POLICY_AND_SECURITY.md)


---

## Historical V4 Baseline Requirements (reference only; superseded where V4.1 refines them)

> **Historical UI exclusion:** Any older requirement below to create a React/TypeScript/Vite frontend, new browser pages, screens, or UI build/test pipeline is superseded by the user decision. These are historical notes, **not implementation tasks**. Preserve existing capabilities for later integration via document 35.

> This is preserved from the earlier planning draft for comparison. The current V4.1 design section, companion docs 30–34, the approved ADR register, and subsequent validated contracts take precedence on changes explicitly addressed in the V4.1 refinement. Historical descriptions of optional vector providers, open SQL fallback, and late Oracle tests are **not** new mandatory decisions.


The following material records relevant requirements from the previously agreed V4 blueprint. The sections above are the detailed module design and take precedence where they add stricter controls. Original V4 is a **proposed architecture**, not independently verified production source.

# 4. Semantic Catalog — The Most Important Component

The semantic catalog determines what business questions mean.

It is more important than simply choosing a better language model.

A physical database schema tells us that a column exists. It does not necessarily tell us how the business expects that column to be interpreted.

## 4.1 What the semantic catalog contains

| Object | Description |
|---|---|
| Business domain | Finance, operations, risk, customer analytics, etc. |
| Business concept | Customer, account, transaction, exposure, assessment |
| Business attribute | Customer identifier, reporting period, status |
| Metric | Approved calculation such as outstanding exposure |
| Dimension | Attributes used for grouping and filtering |
| Synonym | Alternative business terms and abbreviations |
| Formula | Approved mathematical or SQL-compatible expression |
| Grain | What one row or metric result represents |
| Time rule | Current, historical, effective-date and period definitions |
| Source mapping | Physical table and column supplying the information |
| Access policy | Which identities may use a metric or source |
| Relationship | Approved connection between business entities |
| Data lineage | Origin and transformation of the data |
| Approval metadata | Owner, version, status and verification evidence |

## 4.2 Canonical metadata model

We should define a versioned metadata structure with at least these entities:

**TableDefinition**

- Stable table identifier.
- Physical Oracle owner and table or view.
- Business description.
- Domain.
- Grain.
- Approved query usage.
- Column references.
- Data classification.
- Source and approval status.

**ColumnDefinition**

- Stable column identifier.
- Physical Oracle column name.
- Oracle data type, precision and scale.
- Logical data type.
- Business description.
- Nullability.
- Sensitivity classification.
- Allowed operations.
- Synonyms.
- Approved filter behavior.

**RelationshipDefinition**

- Stable relationship identifier.
- Source and target objects.
- Join columns.
- Composite-key support.
- Join cardinality.
- Approved direction and join types.
- Temporal constraints.
- Domain restrictions.
- Provenance and verification status.

**MetricDefinition**

- Metric identifier.
- Business name.
- Description.
- Approved source and expression.
- Aggregation behavior.
- Grain.
- Compatible dimensions.
- Mandatory filters.
- Time rules.
- Null handling.
- Units.
- Owner and approval status.

**CatalogVersion**

- Version identifier.
- Creation timestamp.
- Source checksums.
- Validation result.
- Approval state.
- Published index version.
- Rollback reference.

## 4.3 Business metric example

Use the following fictional example:

**Metric:** Net Sales

**Business definition:** Revenue from completed orders after approved discounts.

The catalog must identify:

- Which orders count.
- How refunds are handled.
- Whether tax is included.
- Which date determines the reporting period.
- Which currency should be used.
- What entity grain is required.
- Which dimensions are allowed.
- Whether historical definitions changed.

We must not expect Gemma to invent those decisions.

## 4.4 Physical source verification

The catalog should be reconciled against the approved Oracle data dictionary.

Verification should cover:

- Physical objects exist.
- Columns exist.
- Data types match.
- Declared keys and constraints are recognized.
- View and synonym dependencies are authorized.
- Join relationships have sufficient evidence.
- Mapped objects are accessible to the reporting identity.
- Missing or changed objects are reported.

The live Oracle data dictionary is authoritative for physical objects and declared constraints.

Approved business documentation is authoritative for metric meanings and business rules.

Both sources are necessary.

## 4.5 Metadata trust levels

Every important definition should have a verification status.

| Status | Meaning | SQL generation |
|---|---|---|
| Certified | Approved by authorized owner and technically validated | Allowed |
| Verified technical | Physical mapping valid, but business approval incomplete | Limited according to policy |
| Proposed | Candidate definition requiring review | Not trusted for governed metrics |
| Inferred | Derived automatically or guessed | Not trusted |
| Deprecated | No longer approved | Blocked |
| Invalid | Contradictory or unresolved | Blocked |

The production system should fail safely when a required metric or relationship is unavailable.

## 4.6 Metadata storage

For the first version, use:

- Versioned JSON/YAML for definitions.
- A local SQLite catalog/index for development where useful.
- An approved enterprise metadata store for production if needed.
- In-memory indexes for request-time lookups.

We do not need a dedicated graph database to store a small join catalog.

---
