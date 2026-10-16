# 19 — Result Integrity, Provenance, Freshness and Human-Readable Answers

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Draft for review; no implementation or company production validation performed.  
**Document owner:** Data + backend + UX  
**Gate:** P0  
**Baseline reference:** V4 research/blueprint supplied on 2026-10-15.  
**Data policy:** Fictional examples only; actual company schema and customer data stay in approved office systems.

> **Core distinction:** this document specifies future behavior. It does not claim that these modules, controls, model benchmarks, or Oracle permissions are already deployed.

## Design specification

## The issue beyond SQL parsing
A query can execute and return numerically plausible data but be wrong because of a stale snapshot, changed metric definition, unintended grain, truncated rows or wrong reporting period. The result formatter must consume a typed `QueryExecutionResult` **and** the validated plan/manifest. No arbitrary LLM narrative can become evidence of correctness.

## Result envelope
`AnswerEnvelope` includes user-facing message, structured result (scalar/table/chart), status, units, requested and resolved period, metric stable IDs/display names, catalog version, query reference ID, data refresh timestamp if authoritative, truncation/pagination flag, applied significant filters and safe warnings. Sensitive physical identifiers remain in authorized internal audit, not public UI by default.

## Freshness rules
Distinguish:
- Query executed at 15:00 (execution timestamp).
- Data source last refreshed at 10:00 (source freshness if documented).
- Data logically represents month-end June (reporting/as-of period).
These must never be conflated. If refresh time is unknown, say unknown—not current or real-time.

## Answer generation
For simple numeric/table results, deterministic templates should state facts from the structured result only. For complex narrative, optional local SLM summary may receive only minimum approved aggregate values and explicit rules; every quantitative claim must reconcile to fields in execution result. Attach uncertainty/warnings rather than inventing missing values.

## Chart quality
A chart specification is derived from typed rows with axis type, unit, period and completeness metadata. Do not plot partial paginated data as an entire distribution unless explicitly labeled subset. Apply role-based masking to display and export paths.

## Auditable proof chain
Persist protected digest/provenance links `question -> catalog snapshot -> resolved metric/join IDs -> ValidatedPlan -> compiled SQL digest -> validator decision -> Oracle execution reference -> AnswerEnvelope`. This makes wrong answers diagnosable without including raw sensitive values in everyday telemetry.

## Regression tests
Precision/rounding, mixed currencies, fiscal boundaries, stale snapshots, NULLs, limited rows, no results, unauthorized columns, result-change race, differing query and data timestamps, and narrative number mismatch.



## V4.1 semantic-view provenance fields
A completed `AnswerEnvelope` records internal `view_id/version`, metric IDs/version, source/reporting-as-of date, source refresh status, result truncation, selected policy/catalog digests, query digest and safe trace reference. Distinguish **reporting as-of date** from **source last-refresh time** from **execution timestamp**; these three values are not interchangeable. If the source refresh time is unknown, show `unknown` rather than inventing currency. Do not disclose hidden physical join paths to unauthorized users.
Use deterministic formatting for numbers/units and provenance. If the SLM narrates, constrain input to typed returned aggregates and verify that quoted numeric facts exist in the result; don't send sensitive full result sets by default.

---

## Deliverables / artifacts to review

AnswerEnvelope schema, provenance manifest, freshness policy, chart/summary rules and result checks

## Acceptance tests and exit criteria

No invented numbers, correct truncation/period/freshness, traceable definition and query ID, masked exports

## Open decisions and evidence required

Where does authoritative data-refresh metadata live? Must the user view generated SQL?

## Related documents

[04](./04_SEMANTIC_CATALOG_AND_GOVERNANCE.md), [10](./10_QUERY_PLAN_DSL_AND_VALIDATION.md), [12](./12_DETERMINISTIC_SQL_COMPILER_AND_TEMPLATES.md), [15](./15_ORACLE_ADAPTER_PREFLIGHT_AND_RESOURCES.md), [16](./16_API_AUTH_AND_ERROR_CONTRACTS.md), [17](./17_FRONTEND_UX_RESULT_TABLES_AND_ACCESSIBILITY.md), [23](./23_OBSERVABILITY_SRE_AND_OPERATIONS.md)


---

## Data quality and provenance sample
```json
{
  "status":"completed",
  "metric":{"id":"net_sales","unit":"USD"},
  "requested_period":"2025",
  "resolved_as_of":"2025-12-31",
  "source_refresh_at":null,
  "execution_at":"2026-10-15T12:00:00Z",
  "truncated":false,
  "catalog_version":"demo-v1",
  "query_reference":"demo-q17"
}
```
A null source refresh timestamp must be rendered as “source refresh unknown,” not “live data.” If the result includes multiple source tables with different last-refresh times, the response needs a defensible aggregation policy (for example, show the oldest participating source), approved by the data owner.

### Quality checks at the formatter boundary
Verify schema of every returned column, Decimal serialization, negative/zero values, currency/percent scaling, timezone, row completeness, display rounding separate from stored precision, user entitlement to individual fields and chart appropriateness. Format deterministic factual sentences; any generated summary is verified against numeric fields and allowed to abstain. Rows of a historical result must retain their snapshot period, not inherit system clock time.

---

## Provenance visibility policy
Separate **internal lineage** (physical schema/SQL digest, verification evidence and authorization decisions) from **user-facing explanation** (approved metric name, date period, unit, source refresh or unknown status, key applied filters, truncation warning). Only privileged auditors may inspect raw physical SQL when organizational policy permits; do not expose joins or restricted object names merely to appear transparent.

### Data freshness decision table
| Condition | Safe displayed text | Consequence |
|---|---|---|
| Refresh timestamp documented and within agreed SLA | “Updated at [source time]” | Continue |
| Refresh timestamp documented but stale | “Data may be stale; last refresh [time]” | Warn or reject by metric policy |
| No refresh provenance | “Source freshness is unavailable” | Do not say live/current |
| Sources refreshed at different times | Per-source times or approved combined method | Warn when incomparable |
| Requested as-of period is historical | “As of [business period]” | Never substitute current date |

### Result numeric integrity
Numeric values are carried as exact Decimal where feasible; display rounding occurs only at rendering. Percentages require explicit denominator and unit. A `null` result cannot be presented as zero unless business definition says so. If row limit truncates an aggregate's constituent rows, do not present the aggregate as complete. For charts, propagate completeness and sampling flags into caption and legend.

---


## V4.2 EWS response translation boundary
Keep the rich typed `AnswerEnvelope`, certified metric, period, freshness and lineage internally. The later EWS adapter maps it to the existing UI's `response` and `results` (array of row objects) safely, preserving server-side masking and truncation; advanced typed charts/provenance controls are deferred because the supplied renderer has no such widgets. `sql_query` must be absent unless an authorized disclosure policy permits it. See [35](./35_EXISTING_UI_INTEGRATION_CONTRACT.md).

---

## Historical V4 Baseline Requirements (reference only; superseded where V4.1 refines them)

> **Historical UI exclusion:** Any older requirement below to create a React/TypeScript/Vite frontend, new browser pages, screens, or UI build/test pipeline is superseded by the user decision. These are historical notes, **not implementation tasks**. Preserve existing capabilities for later integration via document 35.

> This is preserved from the earlier planning draft for comparison. The current V4.1 design section, companion docs 30–34, the approved ADR register, and subsequent validated contracts take precedence on changes explicitly addressed in the V4.1 refinement. Historical descriptions of optional vector providers, open SQL fallback, and late Oracle tests are **not** new mandatory decisions.


The following material records relevant requirements from the previously agreed V4 blueprint. The sections above are the detailed module design and take precedence where they add stricter controls. Original V4 is a **proposed architecture**, not independently verified production source.

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
