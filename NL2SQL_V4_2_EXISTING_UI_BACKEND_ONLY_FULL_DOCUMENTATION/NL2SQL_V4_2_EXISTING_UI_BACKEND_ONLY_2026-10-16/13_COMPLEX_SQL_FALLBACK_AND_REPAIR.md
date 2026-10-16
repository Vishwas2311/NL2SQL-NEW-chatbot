# 13 — Restricted SLM SQL Fallback, Correction and Abstention

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Draft for review; no implementation or company production validation performed.  
**Document owner:** ML + backend security  
**Gate:** P1  
**Baseline reference:** V4 research/blueprint supplied on 2026-10-15.  
**Data policy:** Fictional examples only; actual company schema and customer data stay in approved office systems.

> **Core distinction:** this document specifies future behavior. It does not claim that these modules, controls, model benchmarks, or Oracle permissions are already deployed.

## Design specification

## Invocation gate
Fallback is *not* a universal escape hatch. It is allowed only after certified business grounding, successful `ValidatedPlan`, and a compiler `UnsupportedFeature` class that appears on the approved fallback allowlist. Reject ambiguous metric semantics, missing joins, uncertified sources, denied columns and unsafe operations before any SQL drafting.

## Draft contract
`SqlDraft {sql, bind_variables, output_aliases, referenced_catalog_ids, requested_operation, catalog_version}`. Feed the model a minimized list of approved physical identifiers, exact relationship predicates and applicable metric expressions, never unrestricted data dictionary or customer rows.

## Repair protocol
Attempt 0: generate bounded SQL. Parse/validate in independent service. If `repairable` strictly syntax/allowed rendering issue, return structured validator code and abbreviated safe context for **one** retry. If violation is authorization, metric integrity, missing source or unknown join, stop immediately. Always rerun *all* validators after repair; never allow a model self-certification.

## Execution model
Fallback cannot call database tools itself; there is no arbitrary tool-calling loop. It returns draft SQL only. The trusted SQL validator must mint `ValidatedQuery`, then Oracle preflight executes under read-only identity. The user should not be told a query executed until Oracle confirms.

## Support boundary
Document accepted constructs (e.g., a certified analytic ranking window) and disallowed constructs (unapproved functions, dynamic SQL, DB links, routines, DML/DDL). Extend compiler when repeated valid fallback patterns occur often; use fallback frequency to prioritize features, not to weaken the policy.

## Evaluation
Measure fallback-specific coverage, valid AST rate, true business-result accuracy, incorrect-but-executable SQL, invalid join frequency, repair success, token/time overhead and safe refusal rate. Distinguish compiler misses from SLM mistakes.



## V4.1 restrictive fallback operation policy (supersedes broad 'complex query' language)
**Default flag:** `sql_fallback_enabled = false` for unqualified production domains. Enabling is a reviewed *per-domain/per-operation* decision with DBA, security and semantic-owner approvals. Eligibility requires: validated plan, certified semantic view, verified joins and grain, permitted dataset, budget, and exactly one unsupported compiler *syntax/operator* capability—not missing business meaning or policy proof.
| Operation class | Initial policy | Conditions to promote |
|---|---|---|
| Read-only filtering, grouping, sorting, simple aggregates | Compiler only | N/A |
| Certified analytic windows over one governed view | Deny fallback until tested | Golden result and security/DBA review |
| Approved CTE rewriting for known view/metric | Deny until tested | AST and equivalence cases |
| Correlated subqueries over approved view | Deny until tested | Stronger golden suite and query resource bounds |
| Arbitrary joins, new metrics, raw PL/SQL, DDL/DML, DB links | **Never fallback** | No automatic promotion |
**Important:** a SQL AST allowlist checks form, not numerical business correctness. Every promoted fallback pattern must have independently checked business-result fixtures and bounded Oracle cost. No retry may replace a security denial with an alternative query. One correction attempt maximum by default; repeat full plan/policy validation if IDs or joins change.

---

## Deliverables / artifacts to review

Fallback allowlist, typed draft response, repair state machine, denial error taxonomy and fallback-specific tests

## Acceptance tests and exit criteria

Fallback never runs for failed authorization, uncertain metrics or unsafe joins; bounded repairs; no direct model DB calls

## Open decisions and evidence required

Which advanced SQL operations are genuinely required? What repair budgets meet SLO?

## Related documents

[10](./10_QUERY_PLAN_DSL_AND_VALIDATION.md), [11](./11_LOCAL_SLM_MODEL_CONTEXT_AND_RUNTIME.md), [12](./12_DETERMINISTIC_SQL_COMPILER_AND_TEMPLATES.md), [14](./14_SQL_VALIDATION_POLICY_AND_SECURITY.md), [15](./15_ORACLE_ADAPTER_PREFLIGHT_AND_RESOURCES.md), [24](./24_TEST_DATA_EVALUATION_AND_BENCHMARKS.md)


---

## Fallback security review checklist
Before enabling any fallback capability, QA supplies at least one allowed and three disallowed golden cases. The SQL reviewer confirms function allowlists, CTE/subquery rules, Oracle version behavior, row permissions and resource effects. Each allowed operation has owner, rationale, supported input DSL and test evidence.

**Denied examples:** Compiler cannot express a proprietary metric because it has no certified formula; the system MUST NOT ask Gemma to invent it. A relationship missing a verified join predicate MUST NOT be filled by model inference. A request to call an Oracle stored procedure MUST NOT become permitted because its name appears in schema metadata.

**Positive example:** A window-based rank calculation with approved metric and table/view scope, using a fallback-approved `ROW_NUMBER` operation, may be drafted and checked by AST + semantic validator + preflight; only then execute. A fallback result is not considered correct merely because Oracle returns rows—the golden answer must agree.

---

## Quantitative fallback policy
Fallback is measured as a separate product surface. Keep dashboards for the fraction of valid questions that enter fallback, its median/p95 latency, model output tokens, AST rejection rates, accepted-but-wrong SQL and ratio later absorbed by the deterministic compiler. When fallback usage dominates routine reporting, treat it as a signal of insufficient compiler/semantic coverage rather than increasing agent loops.

### Validation stages for a fallback draft
1. Syntax parse and disallow multiple statements, nested side-effect routines and unauthorized DB links.
2. Resolve every physical table and column to stable allowlisted catalog IDs.
3. Compare joins and filters against plan proof; reject accidental missing constraints.
4. Verify metric expression, grain and time period against catalog semantics.
5. Verify authorization and resource budget before Oracle preflight.
6. Execute only after trusted validator issues a scoped `ValidatedQuery`.

### Error repair decisions
A missing closing parenthesis in an otherwise safe SQL draft may be repairable. A hallucinated table, invented formula, attempted JOIN through an unapproved field or forbidden function is **not** repairable through repeated guessing. Model output after repair is checked from scratch, with the same user permissions and published catalog version.

### Testing examples
Use a certified `ROW_NUMBER` test as the positive case if Oracle version supports it. Negative cases: unapproved `WITH` clause hiding forbidden table, nested `SELECT` on restricted schema, extra `DELETE` statement after semicolon, SQL with invalid join key, SQL returned in markdown fences, a malicious user prompt instructing the fallback to change authorization. All must leave the spy executor uncalled.

---

## Historical V4 Baseline Requirements (reference only; superseded where V4.1 refines them)

> **Historical UI exclusion:** Any older requirement below to create a React/TypeScript/Vite frontend, new browser pages, screens, or UI build/test pipeline is superseded by the user decision. These are historical notes, **not implementation tasks**. Preserve existing capabilities for later integration via document 35.

> This is preserved from the earlier planning draft for comparison. The current V4.1 design section, companion docs 30–34, the approved ADR register, and subsequent validated contracts take precedence on changes explicitly addressed in the V4.1 refinement. Historical descriptions of optional vector providers, open SQL fallback, and late Oracle tests are **not** new mandatory decisions.


The following material records relevant requirements from the previously agreed V4 blueprint. The sections above are the detailed module design and take precedence where they add stricter controls. Original V4 is a **proposed architecture**, not independently verified production source.

# 12. Controlled SLM SQL Fallback

The SQL fallback is essential for maintaining flexibility, but must be tightly restricted.

## 12.1 When fallback is allowed

Fallback may run when:

- The query plan is semantically valid.
- Required metrics and joins are verified.
- The compiler explicitly reports an unsupported SQL construct.
- The operation is included in the fallback allowlist.
- The user has required permissions.
- The request fits resource policies.

## 12.2 What the fallback receives

Only:

- The validated query plan.
- Approved table and column definitions.
- Required join predicates.
- Applicable metric definitions.
- Oracle SQL requirements.
- Prohibited operation rules.
- Output constraints.

## 12.3 What the fallback cannot do

It cannot:

- Invent a new business metric.
- Choose an unauthorized table.
- Ignore mandatory row filters.
- Join unrelated tables.
- Execute database operations itself.
- Use unapproved external tools.
- Bypass the SQL validator.

## 12.4 Repair policy

Use a bounded repair workflow.

Default proposal:

- Initial SQL-generation attempt.
- One error-directed repair when the error is safely correctable.
- Stop if validation still fails.

The application should record the failure category without exposing sensitive SQL or customer data in ordinary logs.

---
