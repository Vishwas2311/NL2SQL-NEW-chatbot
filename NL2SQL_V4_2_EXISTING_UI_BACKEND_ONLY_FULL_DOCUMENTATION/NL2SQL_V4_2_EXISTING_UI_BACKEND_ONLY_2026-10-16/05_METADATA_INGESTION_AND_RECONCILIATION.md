# 05 — Metadata Ingestion, Verification, Index Publishing and Drift

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Draft for review; no implementation or company production validation performed.  
**Document owner:** Data engineer + DBA  
**Gate:** P0  
**Baseline reference:** V4 research/blueprint supplied on 2026-10-15.  
**Data policy:** Fictional examples only; actual company schema and customer data stay in approved office systems.

> **Core distinction:** this document specifies future behavior. It does not claim that these modules, controls, model benchmarks, or Oracle permissions are already deployed.

## Design specification

## Source adapters
Design a `MetadataSourceAdapter` interface with `load_snapshot()`, `source_signature()`, and `describe_provenance()`. Implement JSON/YAML fixture importer locally. Office-only adapters can read approved Oracle metadata, curated dictionaries or owner-reviewed spreadsheet extracts. Do not make proprietary source formats central to the canonical contract.

## ETL stages
**Extract (approved) → parse → normalize → resolve stable IDs → reconcile physical objects → validate joins/metrics/permissions → build catalog → build exact/BM25 index → optional embeddings → sign/publish snapshot → notify caches.**

## Reconciliation dimensions
- Owner/schema-qualified physical names; allowed views and synonyms; identifier case and quoting.
- Oracle native types, precision, scale, nullability, PK, FK and unique constraints (declared vs inferred distinguished).
- Join predicate completeness, composite keys, cardinality/temporal constraints and domain restriction.
- Formula dependencies and missing dimensions, incorrect date sources or undefined business filters.
- Sensitive sample values: exclude them from portable or model-facing indexes by default.
- Complete-versus-partial coverage: quantify unmapped tables/columns/metrics and fail gated publication on required gaps.

## Sample validation report format
| Field | Meaning |
|---|---|
| source_digest | Checksum, without leaking the source payload |
| catalog_version | Candidate immutable catalog ID |
| object_counts | Tables, columns, metrics, edges, mappings |
| resolved_count / blocked_count | Technical coverage after verification |
| unresolved_refs | Stable internal IDs + reason; reviewed with proper access |
| security_approval | Named authorized reviewer status |
| index_digest | Exact/lexical/vector index version |
| published_at | Timestamp when immutable snapshot went live |

## Zero-downtime publication
Construct the new snapshot in isolation. Run schema validation and synthetic consistency checks. Publish atomically with catalog and retrieval index sharing one version identifier. Requests in flight retain their old immutable snapshot. Failed publication must leave old snapshot active. On restart load only a signed/approved snapshot; reject incomplete metadata rather than silently improvising relationships.

## Drift monitoring
Office integration should compare approved metadata with Oracle catalog at agreed cadence and report deltas (new/removed/renamed objects, changed types, policy/grants, changed metric owner). Schema drift alerts should not automatically authorize new objects for generation. Reconciliation is an administrative action, not a per-chat activity.



## V4.1 importer contract for semantic views and early Oracle fixtures
Extend `MetadataSourceAdapter.load_snapshot()` to return `SemanticViewDefinition` records and verification evidence. A view may reference a *certified existing Oracle view* or a *logical compiler-side view*. Both resolve to stable approved table/column IDs and join predicates. Detect cycles across metric → view → derived field dependencies; reject incomplete mappings, forbidden owner/schema changes, or stale index digests.
Publish a single atomic tuple `(catalog_digest, view_digest, lexical_index_digest, optional_vector_digest, join_graph_digest, policy_digest)`; each query pins one snapshot. A changed view invalidates dependent compiled templates, caches, retrieval entries and golden tests. Import does not automatically certify workbook/Graphify facts. Oracle snapshot verification takes place only in a permitted enterprise network; generic synthetic fixtures exercise the same mapping lifecycle.
**Drift acceptance:** missing physical column, changed Oracle type, source-view replacement, metric formula revision or altered RLS/VPD policy blocks dependent view activation and marks impacted tests. Oracle dialect smoke tests should be available early via an approved test environment (see [33](./33_ORACLE_EARLY_COMPATIBILITY_AND_PREFLIGHT.md)).

---

## Deliverables / artifacts to review

Import adapters, validation report, provenance register, publish/rollback runbook and drift tests

## Acceptance tests and exit criteria

Load synthetic JSON; reject missing target columns, duplicate IDs, invalid metric expressions, stale index; atomic snapshot rollback

## Open decisions and evidence required

Oracle dictionary access rights? Metadata refresh frequency? Does production allow scheduled catalogs or only manual publication?

## Related documents

[04](./04_SEMANTIC_CATALOG_AND_GOVERNANCE.md), [06](./06_RETRIEVAL_LEXICAL_VECTOR_AND_RANKING.md), [07](./07_JOIN_GRAPH_GRAIN_AND_TEMPORAL_RULES.md), [21](./21_SECURITY_PRIVACY_THREAT_MODEL.md), [23](./23_OBSERVABILITY_SRE_AND_OPERATIONS.md)


---

## Detailed ingestion contract and failure semantics
A source adapter returns an immutable `ImportBatch {batch_id, source_type, extraction_time, source_hash, metadata_objects, diagnostics}`. A normalizer never replaces owner-qualified physical names with unqualified identifiers. A reconciler accepts only internal admin credentials; it must not run during a normal chat. Approval records reference the exact normalized output digest, not merely the input spreadsheet filename.

**Publish algorithm:** Validate schema (`Pydantic`/JSON schema) → verify cross-references → reconcile with approved physical oracle dictionary → apply certification and access rules → construct immutable catalog → rebuild exact/lexical/embedding indexes **using identical catalog digest** → run smoke queries on synthetic fixtures → obtain required approval → atomically update active pointer. On any failed step keep previous active pointer and preserve a diagnostic-only rejected candidate.

**Provenance policy:** For every imported metric/relationship store `origin_kind`, `source_snapshot`, `steward_id`, `reviewed_at`, `physical_verification`, `confidence_class` and `effective_interval`. A spreadsheet- or graph-mined relationship cannot upgrade itself from `proposed` to `certified` because an embedding or graph visualization agrees. Changes in a column type or metric formula invalidate dependent compiled templates and cache entries.

| Adversarial fixture | Expected outcome |
|---|---|
| Missing physical target column | Block affected relationship/metric publication |
| Cyclic formula dependency | Reject dependency graph and show cycle IDs |
| Same metric ID with conflicting formulas | Require explicit steward resolution |
| Changed Oracle type | Quarantine dependent expressions; previous active snapshot remains |
| Source index built against old metadata | Refuse activation due to digest mismatch |
| Unauthorized sensitive sample values | Exclude from portable, vector and model-context material |

**Signoff evidence:** A machine-readable reconciliation report, signed catalog hash, count/coverage matrix by business domain, and a rollback drill. Production publication must also record which principal performed the administrative action; it is not a user chatbot route.

---

## Historical V4 Baseline Requirements (reference only; superseded where V4.1 refines them)

> **Historical UI exclusion:** Any older requirement below to create a React/TypeScript/Vite frontend, new browser pages, screens, or UI build/test pipeline is superseded by the user decision. These are historical notes, **not implementation tasks**. Preserve existing capabilities for later integration via document 35.

> This is preserved from the earlier planning draft for comparison. The current V4.1 design section, companion docs 30–34, the approved ADR register, and subsequent validated contracts take precedence on changes explicitly addressed in the V4.1 refinement. Historical descriptions of optional vector providers, open SQL fallback, and late Oracle tests are **not** new mandatory decisions.


The following material records relevant requirements from the previously agreed V4 blueprint. The sections above are the detailed module design and take precedence where they add stricter controls. Original V4 is a **proposed architecture**, not independently verified production source.

# 5. Schema Discovery and Metadata Loading

## 5.1 Development-time schema loading

The local application will start with synthetic schema fixtures.

Examples of test tables:

- Customers.
- Accounts.
- Orders.
- Payments.
- Customer Risk Assessments.
- Customer Status History.
- Transactions.
- Reporting Periods.

Synthetic fixtures must include:

- Primary and foreign keys.
- Composite keys.
- One-to-many relationships.
- Missing values.
- Duplicate-sensitive joins.
- Historical rows.
- Effective-date rules.
- Multiple candidate join paths.
- Ambiguous column names.
- Restricted fields.

These cases are necessary to test correctness.

## 5.2 Enterprise schema loading

In the approved company environment, the metadata-import process should read company-approved source definitions.

Depending on access and policy, this could include:

- Oracle metadata views.
- Approved schema JSON.
- Existing data dictionaries.
- Approved business metric definitions.
- Approved join documentation.

The importer should convert these sources into the canonical catalog.

It should not change Oracle structures.

## 5.3 Import validation stages

1. Validate source structure.
2. Normalize types and identifiers.
3. Check duplicate and conflicting definitions.
4. Resolve table-column references.
5. Verify relationships.
6. Validate metric dependencies.
7. Apply access classifications.
8. Generate a new catalog version.
9. Build indexes.
10. Run catalog consistency tests.
11. Publish atomically after approval.

If import validation fails, preserve the previous approved snapshot.

## 5.4 Refresh strategy

Metadata refresh should be scheduled or explicitly triggered, not automatically performed on every chat request.

The chatbot should use a stable catalog version for an individual query.

This prevents situations where retrieval uses one schema version but SQL validation uses another.

---
