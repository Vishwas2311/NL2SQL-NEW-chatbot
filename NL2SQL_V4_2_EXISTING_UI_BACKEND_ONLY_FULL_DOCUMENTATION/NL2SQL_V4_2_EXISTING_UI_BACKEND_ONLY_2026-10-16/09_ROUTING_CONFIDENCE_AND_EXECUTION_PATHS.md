# 09 — Intent Routing, Confidence Gates and Three-Path Decisions

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Draft for review; no implementation or company production validation performed.  
**Document owner:** AI engineer + backend architect  
**Gate:** P0  
**Baseline reference:** V4 research/blueprint supplied on 2026-10-15.  
**Data policy:** Fictional examples only; actual company schema and customer data stay in approved office systems.

> **Core distinction:** this document specifies future behavior. It does not claim that these modules, controls, model benchmarks, or Oracle permissions are already deployed.

## Design specification

## Routing design
A single orchestrator chooses among fast certified templates (0 SLM calls), normal typed SLM planning (usually 1 call), and complex constrained SQL fallback (only when the compiler reports a supported capability gap). Model call numbers are targets, not guarantees; they must be measured. Resist turning the router into its own LLM agent without evidence.

## Decision table
| Question state | Route | Action |
|---|---|---|
| Unambiguous certified template + validated slots | Fast | Compile/validate/execute; skip Gemma |
| Sufficient verified catalog + flexible phrasing | Normal | One typed Gemma plan; validate and compile |
| Valid plan + compiler unsupported but fallback-allowlisted operation | Complex | Restricted SQL generation then full validation |
| Competing plausible metrics/periods/entities | Clarify | Ask user; never force highest cosine score |
| Missing certified formula, join or permission | Stop | Unsupported or access-denied |
| Model, index or Oracle unavailable | Degraded/error | Fail safely; conditionally allow certified path only |

## Confidence is a decision, not one scalar
Signals include: exact certified concept match, domain match, required source/relationship coverage, ambiguity count, metric approval, supported DSL operators and permission proof. Cosine similarity should not be labeled a probability. Set operational thresholds using a labeled calibration corpus; monitor false-positive automatic routing separately from unnecessary clarifications.

## Clarification semantics
Return a typed `ClarificationRequest` with reason ID, approved choices if safe, unresolved slot(s), session reference and expiration. Never expose privileged hidden metadata. On response, rerun authorization and check catalog version; retain only minimal prior slots. Avoid letting clarification reply become arbitrary SQL code.

## Budgeted route control
Each request has one trace ID, bounded total attempts, deadline, token budget and SQL execution allocation. A repaired plan that changes metric IDs or joins must rerun grounding and authorization. The router must not retry repeatedly until a denial disappears.

## KPI dashboard
Track router precision/recall per path, semantic ambiguity resolution, wrong fast-path matches, unsupported-but-valid query proportion, retries, calls/query, user-perceived latency and business-result accuracy separately for each path.



## V4.1 routing order and uncertainty budget
`auth → certified template gate → domain/metric retrieval → certified semantic-view coverage check → joins/values → (SLM if needed) → validate plan → compile → fallback only for approved grammar gaps`. For clarity: short-circuiting a valid template **does not skip SQL/business/policy/preflight checks**.
The router must not treat retrieval rank or the model's self-reported confidence as sufficient proof. Hard gates: approved view, certified metric, complete time/grain specification, legal selected fields, current authorizations, valid value resolution and supported operation. A failed hard gate triggers clarification, unsupported response or denial—not vector over-search or fallback to raw SQL.
Collect separate coverage outcomes by route: fast path, compiler, controlled fallback, clarification, authorized unsupported, and denied. Use a shared request deadline across any retrieval expansion, model call and SQL preflight.

---

## Deliverables / artifacts to review

Routing state machine, confidence/ambiguity rubric, path contracts and test decision matrix

## Acceptance tests and exit criteria

Safe path choice; no unauthorized fallback; no false fast-path execution on near matches

## Open decisions and evidence required

What certified reports exist? Which complex SQL constructs can be supported by fallback?

## Related documents

[04](./04_SEMANTIC_CATALOG_AND_GOVERNANCE.md), [06](./06_RETRIEVAL_LEXICAL_VECTOR_AND_RANKING.md), [07](./07_JOIN_GRAPH_GRAIN_AND_TEMPORAL_RULES.md), [08](./08_ENTITY_AND_VALUE_RESOLUTION.md), [10](./10_QUERY_PLAN_DSL_AND_VALIDATION.md), [11](./11_LOCAL_SLM_MODEL_CONTEXT_AND_RUNTIME.md), [12](./12_DETERMINISTIC_SQL_COMPILER_AND_TEMPLATES.md), [13](./13_COMPLEX_SQL_FALLBACK_AND_REPAIR.md)


---

## Detailed routing invariants
The first route stage performs cheap normalization (trim, locale/case rules), security scope resolution and known-template lookup. If not certified, it calls retrieval/value resolution and evaluates completeness. No model is asked to make a standalone “confidence percentage” decision. If the catalog cannot prove a required join, that is a hard stop regardless of the language model's confidence.

| Signal | True means | Impact |
|---|---|---|
| Unique certified metric | Exactly one approved business definition | Fast/normal eligible |
| Verified join closure | All needed tables linked by approved predicates | Normal/complex eligible |
| Unresolved value count > 0 | Entity reference ambiguous | Clarify before SQL |
| Metric not certified | Missing approved calculation | Unsupported; no fallback |
| Compiler unsupported feature | DSL plan valid but renderer lacks operation | Complex path only if allowed |
| Permission mismatch | Selected source outside entitlements | Deny; no retries |

**Calibration experiment:** Hold out questions with similar metric wording (“outstanding balance,” “total exposure,” “approved credit limit”). Evaluate false high-confidence automatic choice and clarification rate. Reject a proposed threshold that improves speed by increasing incorrect metric selection. Report performance separately per path, so zero-SLM templates do not conceal slow general questions.

---

## Historical V4 Baseline Requirements (reference only; superseded where V4.1 refines them)

> **Historical UI exclusion:** Any older requirement below to create a React/TypeScript/Vite frontend, new browser pages, screens, or UI build/test pipeline is superseded by the user decision. These are historical notes, **not implementation tasks**. Preserve existing capabilities for later integration via document 35.

> This is preserved from the earlier planning draft for comparison. The current V4.1 design section, companion docs 30–34, the approved ADR register, and subsequent validated contracts take precedence on changes explicitly addressed in the V4.1 refinement. Historical descriptions of optional vector providers, open SQL fallback, and late Oracle tests are **not** new mandatory decisions.


The following material records relevant requirements from the previously agreed V4 blueprint. The sections above are the detailed module design and take precedence where they add stricter controls. Original V4 is a **proposed architecture**, not independently verified production source.

# 3. Three Query Execution Paths

The architecture will support three paths.

## Path A — Deterministic fast path

Used when the user asks a question that unambiguously matches an approved query template or certified metric operation.

**Flow:**

User question → exact intent match → validated parameters → approved query template → SQL validation → Oracle → answer.

**Gemma calls:** Zero.

Example:

"Show the latest five reporting periods."

If an approved query template already supports this operation, the system can execute it without invoking the SLM.

### Requirements

- Match only approved templates.
- Extract and validate parameters.
- Confirm required user permissions.
- Verify the current catalog/template version.
- Never confuse a merely similar question with a certified match.
- Route ambiguous wording to the normal path.

This path is intended to minimize latency for frequent queries.

## Path B — Structured SLM planning

This is our default path for flexible business questions.

**Flow:**

Question → semantic retrieval → verified relationships → Gemma generates structured plan → validate plan → SQL compiler → validate SQL → Oracle → answer.

Example:

"Find the top ten customers with the highest exposure last quarter."

Gemma selects an approved metric, grouping, filters, sorting and limit.

The SQL compiler determines the actual Oracle tables, joins, formulas and SQL syntax.

### Benefits

- Less SQL text generated by Gemma.
- Better consistency across repeated queries.
- Easier validation.
- Less dependence on the model knowing Oracle-specific syntax.
- Easier model replacement.
- Clearer debugging when the answer is incorrect.

## Path C — Constrained complex SQL fallback

Some queries require operations outside the deterministic compiler's supported scope.

Examples may include complex analytic windows, unusual correlated subqueries or specialized temporal analysis.

**Flow:**

Question → verified grounding → structured plan → compiler reports unsupported operation → constrained SLM SQL generation → independent validation → Oracle → answer.

### Strict rules

- The model may reference only authorized, approved database objects.
- Required business formulas must come from the semantic catalog.
- The model cannot invent joins or new metric definitions.
- Generated SQL must pass all normal validation.
- Retries must be bounded.
- Unsupported or ambiguous cases must be clarified or rejected.

**Important:** Fallback exists for SQL-expression flexibility, not to bypass governance or missing business definitions.

---

---

# 8. Intent Router and Query Understanding

## 8.1 What the intent router does

The router identifies the type of user request before selecting a query strategy.

Supported categories:

| Intent | Example | Handling |
|---|---|---|
| Lookup | Show customer details | Filtered selection |
| Aggregation | Count high-risk customers | Approved aggregate |
| Ranking | Top ten accounts by exposure | Aggregate + sort + limit |
| Comparison | Compare this year with last year | Period-aware query |
| Trend | Monthly exposure trend | Time-series query |
| Historical | Risk status as of June | Effective-date logic |
| Multi-table | Customers with several indicators | Verified joins |
| Follow-up | What about last quarter? | Session-context resolution |
| Ambiguous | Show high exposure customers | Clarify undefined threshold |
| Unsupported | Request unavailable information | Explain limitation |
| Disallowed | Attempt to modify database records | Reject |

## 8.2 Routing without unnecessary SLM calls

A simple deterministic rule or validated intent template should be used when it is sufficient.

For more flexible questions, the router uses the SLM.

Avoid creating a separate SLM call solely for intent classification unless the evaluation proves that the extra call is beneficial.

For many requests, intent detection and structured query planning can happen in the same model call.

## 8.3 Clarification conditions

Ask for clarification when:

- Two metrics have different valid definitions.
- The requested time period is unclear.
- A requested dimension is not compatible with the metric.
- Multiple approved join paths yield different answers.
- A required customer or entity is unidentified.
- A business threshold is unspecified and no approved default exists.

Clarification is preferable to producing confident but incorrect SQL.

---
