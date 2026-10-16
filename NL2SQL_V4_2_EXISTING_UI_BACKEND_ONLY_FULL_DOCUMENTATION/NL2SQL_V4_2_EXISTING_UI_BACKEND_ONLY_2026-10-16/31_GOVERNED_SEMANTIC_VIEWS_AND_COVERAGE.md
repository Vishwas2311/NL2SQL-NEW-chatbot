# 31 — Governed Semantic Views, Grain-Safe Analytics and Coverage Contracts

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Proposed design. **Owners:** Business metric steward, DBA, compiler engineer, security. A semantic view is a *logical governed abstraction* by default, not an instruction to create Oracle DDL.

## Purpose and boundary
The existing V4 catalog, metric registry and verified physical join graph remain authoritative. **Semantic views** expose smaller, business-specific sets of metrics and dimensions with a fixed reporting grain, approved temporal semantics and source lineage. They reduce repeated raw-schema reasoning for a 12B SLM and enable safer deterministic SQL compilation. They do **not** supersede security policies, physical data dictionary checks or underlying join constraints.

## Source of truth and lifecycle
```
Physical Oracle metadata + approved business rules + authorized join evidence
  → canonical typed catalog
  → proposed SemanticViewDefinition
  → grain/metric/time/policy tests + owner approval
  → certified versioned view snapshot
  → compiled templates/retrieval documents/graph subpaths
  → QueryPlan selecting stable semantic_view_id
```
A proposed spreadsheet or graph relationship is never automatically certified. Physical views require DBA change control and grants; logical views are compiler mappings. One catalog snapshot pins all dependencies per request.

## Typed semantic-view model
| Field | Type / constraints |
|---|---|
| `id`, `version`, `status` | stable string, semver-like version, `draft/certified/retired` |
| `domain_id`, `business_entity_id` | certified references, one business scope |
| `grain` | certified entity key set; cannot be guessed by SLM |
| `source_kind` | `logical` or `approved_oracle_view` |
| `source_ref` | catalog-approved mapping ID; never free-form user SQL |
| `metrics`, `dimensions`, `filters` | allowlisted ID references and type contracts |
| `required_relationships` | verified physical joins with composite keys, grain and temporal predicates |
| `mandatory_predicates` | business + auth enforced with bind-safe expressions and database policy |
| `time_roles` | reporting period, source snapshot, effective start/end; defaults documented |
| `aggregation_policy` | additive/semi/non-additive, pre-aggregation and fan-out controls |
| `lineage`, `data_classification` | physical and logical origins; field sensitivity |
| `owner`, `certification_evidence`, `effective_dates` | named reviewers, golden results, history |

## Fictional example: customer exposure view (not real bank data)
```yaml
id: customer_exposure
version: 1.0.0
status: proposed
source_kind: logical
domain_id: credit_reporting
business_entity_id: customer
grain: [customer_id, reporting_date]
dimensions: [customer_id, reporting_date, risk_band]
metrics: [outstanding_exposure]
required_relationships: [customer_to_loan_snapshot]
mandatory_predicates: [authorized_customer_scope]
time_roles: {as_of: reporting_date, snapshot: reporting_date}
aggregation_policy: {outstanding_exposure: additive_across_customers_not_time}
data_classification: internal_restricted
```
This example cannot be promoted until the metric's exact physical expression, date selection and policy have passed review. A name alone does not confer certification.

## Grain and multiple-fact defense
For each view, explicitly document what **one logical row** means. Two independent one-to-many datasets cannot be joined at their raw grain without risking multiplied totals. If a valid question combines facts with different grains, the planner either pre-aggregates each fact to a common key/as-of period, uses a separately approved composite view, or rejects/clarifies. Do not rely on `DISTINCT` as a universal fix. Historical and snapshot semantics must select the approved effective record, not merely the largest timestamp.

## View-selection algorithm
Given a permission-scoped question and retrieved metric IDs: (a) enumerate certified views exposing required metrics/compatible dimensions and time roles; (b) ensure policy and source mappings valid; (c) check grain and join proof; (d) prefer the *minimal covering view* with measured reliability; (e) if several valid views yield different semantics, clarify; (f) if no view covers the request, compile from catalog relationship proofs only if a certified general-plan path exists; otherwise unsupported. A query plan can reference one or multiple *approved* views only when the cross-view relationship/grain is itself certified.

## Physical Oracle view versus logical compiler view
| Choice | Advantage | Trade-off / gate |
|---|---|---|
| Logical view in catalog | No Oracle schema DDL; fast iteration, versioned with compiler | Must prove compiled joins, date rules and optimizer behavior |
| Existing approved Oracle view | Stable SQL interface, DBA-controlled access and potential optimizer benefits | May constrain dynamic filters or hide time/grain assumptions |
| Create new Oracle view | Can simplify access and governance | Requires DBA, security/performance approval and change-management rollout |
No automatic view DDL is permitted by the chatbot; V4 release does not assume materialized views or new database privileges.

## Certification checklist and negative cases
- [ ] Business owner certifies metric formula and units, grain, dimensions and fiscal/as-of rules.
- [ ] DBA verifies physical tables/views, composite keys, relationship cardinalities and Oracle dialect.
- [ ] Security verifies database-enforced row/column scope and source sensitivity.
- [ ] Golden cases test zero/NULL, changing snapshots, duplicate-many joins, fiscal boundaries and unauthorized dimensions.
- [ ] Compiler proof includes view ID/version, metric versions, source IDs, required predicates, data freshness and output types.
- [ ] View/index/template refresh published atomically with digest; old snapshots rollback safely.

## Failure taxonomy
`UNCERTIFIED_VIEW`, `VIEW_MAPPING_MISSING`, `VIEW_GRAIN_CONFLICT`, `VIEW_TIME_ROLE_AMBIGUOUS`, `VIEW_POLICY_DENIED`, `VIEW_VERSION_STALE`, `UNSUPPORTED_VIEW_COMBINATION` all fail before Oracle execution. Treat these as semantic errors, **not** reasons for unrestricted SQL fallback.

## Deliverables / acceptance
A versioned `SemanticViewDefinition` JSON Schema/Pydantic model, two synthetic certified views with different grains, lineage/proof report, 20+ targeted join/metric/temporal negative/positive fixtures (initial target), and a measured coverage report showing whether views improve results and when they restrict otherwise answerable questions. Cross-reference 04/05/07/09/10/12/14/19/24.
