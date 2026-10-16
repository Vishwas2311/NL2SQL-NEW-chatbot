# 11 — Gemma 4 12B, Model Adapters, Prompt/Context and Runtime

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Draft for review; no implementation or company production validation performed.  
**Document owner:** ML engineering + platform  
**Gate:** P0  
**Baseline reference:** V4 research/blueprint supplied on 2026-10-15.  
**Data policy:** Fictional examples only; actual company schema and customer data stay in approved office systems.

> **Core distinction:** this document specifies future behavior. It does not claim that these modules, controls, model benchmarks, or Oracle permissions are already deployed.

## Design specification

## Model independent interface
Implement `plan(question, GroundingContext, CompactSessionState, deadline) -> PlanningResult`, `fallback_sql(ValidatedPlan, AllowedSourceContext, deadline) -> SqlDraft`, `capabilities()`, `tokenize_count()`, `health()`. Providers must preserve request-level trace IDs and enforce private endpoint allowlists. The model is untrusted, and its responses must never call the DB directly.

## Runtime policies
Gemma 4 12B is the initial baseline, not the final proven best. Confirm the exact instruction-tuned checkpoint and quantization/runtime support. For Apple Silicon development, benchmark an MLX-compatible provider. For approved server hardware, benchmark vLLM/SGLang or another internally approved OpenAI-compatible runtime. Quantization, KV cache, max context and concurrency are runtime knobs; avoid equating disk capacity with active model or KV memory.

## Grounding context builder
Context is constructed from an immutable published catalog version: user question, **permission-filtered** certified metric descriptions, required dimensions, relevant tables/columns, verified joins, temporal/grain rules, small safe session slots and strict output schema. Do not add all columns or the full chat history. Avoid real row samples unless a specific approved semantic task requires them; prefer fictional examples.

## Prompt skeleton (conceptual)
- Role: interpret natural language into `QueryPlan` only.
- Allowed IDs: explicit list of certified metrics/dimensions/filter operators.
- Required constraints: catalog version, temporal defaults, compulsory filters and relationships.
- Output: typed JSON, no natural-language extra text.
- Abstain: ask clarification on ambiguity; do not invent names, joins, functions or business definitions.

## Error handling
Malformed/truncated JSON -> parse error -> at most one bounded structural repair or clarification. Timeout -> safe service error. An unknown metric ID -> plan validator rejection, not an attempt to teach the model unauthorized schema. Prevent chain-of-thought or free-form verbose text from filling output unnecessarily; structured generation capability is measured per runtime.

## Benchmarks
Test structured-plan validity, accuracy/coverage, tool/API calling where relevant, p50/p95 latency, prefill and decode times, prompt/output tokens, peak memory and concurrent requests. Compare at least one alternate small model with identical retrieval and compiler, never on different test corpora.



## V4.1 model context, role and candidate selection
Do **not** make Gemma the physical-schema search engine by default. Feed the SLM a minimal, permission-filtered bundle of certified semantic view IDs, metric/dimension descriptions, allowed operations, reporting time rules and join/grain proof references. The model produces a typed *plan*, not business formula SQL. If deterministic template routing recognizes the question, skip the SLM. Keep the model provider swappable and calibrate prompt/context budgets with actual runtime telemetry.
Benchmark **Gemma compact schema/no-embedding** against **exact/BM25** and **optional local embedding + FAISS** for the same question set; compare a second company-approved SLM separately while holding catalog/compiler/retrieval fixed. No company schema, customer data or business prompts to public inference endpoints without explicit authorization. Prefer schema IDs and example templates over unrestricted conversational history.

---

## Deliverables / artifacts to review

Provider contract, prompt catalog, token policy, local serving configurations and model benchmark harness

## Acceptance tests and exit criteria

Canonical JSON under timeouts, no external endpoints, provider substitution with unchanged business results

## Open decisions and evidence required

Allowed model weights/licenses? Apple/local GPU limits and target production GPU? Output JSON constrained decoding supported?

## Related documents

[06](./06_RETRIEVAL_LEXICAL_VECTOR_AND_RANKING.md), [09](./09_ROUTING_CONFIDENCE_AND_EXECUTION_PATHS.md), [10](./10_QUERY_PLAN_DSL_AND_VALIDATION.md), [12](./12_DETERMINISTIC_SQL_COMPILER_AND_TEMPLATES.md), [13](./13_COMPLEX_SQL_FALLBACK_AND_REPAIR.md), [20](./20_CACHING_LATENCY_AND_RESOURCE_BUDGETS.md), [22](./22_PRIVATE_DEPLOYMENT_INFRA_AND_FULCRUM.md)


---

## Prompt injection and model output tests
The model must treat metadata descriptions and the user question as data, not instructions to run tools or reveal secrets. Never include model credentials, DB password or private network details in prompts. Enforce a strict structured response; don't accept content after/before the JSON as SQL commands. A generated metric ID absent from the allowed enum is a plan error.

### Token profiles for evaluation, not fixed claims
Record per-query question tokens, selected metric metadata, selected column/edge definitions, session-slot tokens and output schema size. Compare exact/BM25-only and embedding-assisted prompts using the same Gemma model. Measure prefill latency separately from output decoding, KV memory at 8K/16K contexts and concurrent users, and whether extending context actually improves accuracy. More context is not automatically better.

### Adapter fault injection
Simulate inference service unavailable, 60-second timeout, truncated JSON, unknown tool call, malformed Unicode, extra explanatory prose, invalid field ID, out-of-memory and concurrent request saturation. If model dies, the already-validated certified fast path may continue only if the executor and authorization checks remain healthy. Normal/complex requests must return safe service statuses, not raw model errors.

---

## Historical V4 Baseline Requirements (reference only; superseded where V4.1 refines them)

> **Historical UI exclusion:** Any older requirement below to create a React/TypeScript/Vite frontend, new browser pages, screens, or UI build/test pipeline is superseded by the user decision. These are historical notes, **not implementation tasks**. Preserve existing capabilities for later integration via document 35.

> This is preserved from the earlier planning draft for comparison. The current V4.1 design section, companion docs 30–34, the approved ADR register, and subsequent validated contracts take precedence on changes explicitly addressed in the V4.1 refinement. Historical descriptions of optional vector providers, open SQL fallback, and late Oracle tests are **not** new mandatory decisions.


The following material records relevant requirements from the previously agreed V4 blueprint. The sections above are the detailed module design and take precedence where they add stricter controls. Original V4 is a **proposed architecture**, not independently verified production source.

# 9. Gemma 4 12B Integration

## 9.1 Model responsibility

Gemma's main responsibility is to understand flexible natural language and select approved query concepts.

It should not serve as the authority for physical schema definitions or database security.

## 9.2 Model abstraction

We should build a model-provider interface rather than directly connecting all application modules to one specific inference engine.

Conceptual methods:

- `generate_plan()`
- `generate_sql_fallback()`
- `repair_structured_output()`
- `get_capabilities()`
- `count_tokens()`
- `health_check()`

Implementations can include:

- Gemma through a local MLX-compatible runtime.
- Gemma through an approved vLLM server.
- Another approved OpenAI-compatible inference endpoint.
- A mock model used in tests.

## 9.3 Model-selection strategy

Gemma 4 12B is the baseline, not an irreversible decision.

Benchmark it against at least one alternative small model using identical tests.

Evaluate:

- Structured-plan correctness.
- SQL fallback execution accuracy.
- Business interpretation.
- JSON validity.
- Prompt tokens.
- Output tokens.
- Median and p95 latency.
- Peak memory usage.
- Concurrent-user throughput.
- Model/runtime compatibility.

Do not select a model solely from public benchmark rankings.

## 9.4 Structured output

Gemma should normally output a typed query plan.

Example using fictional metadata:

```json
{
  "version": "1.0",
  "intent": "ranking",
  "metric_id": "loan_exposure",
  "dimensions": ["customer"],
  "filters": [
    {
      "field_id": "reporting_period",
      "operator": "previous_quarter"
    }
  ],
  "sort": [
    {
      "field_id": "loan_exposure",
      "direction": "desc"
    }
  ],
  "limit": 10
}
```

The model must select only supported identifiers and operators.

A valid JSON response is necessary but not sufficient: semantic validation must verify that every field and combination is allowed.

## 9.5 Query plan schema

Use Pydantic models with explicit fields for:

**QueryPlan**

- Version.
- Intent.
- Metric references.
- Dimensions.
- Filter expressions.
- Date interpretation.
- Grouping.
- Sorting.
- Limits.
- Optional comparison specification.
- Optional analytic operation.
- Required clarification.
- Catalog version reference.

**FilterExpression**

- Approved field ID.
- Allowed operator.
- Typed value or semantic date expression.
- Optional nested boolean grouping.

**PlanningResult**

- Status: ready, clarification_required, unsupported or invalid.
- Query plan when ready.
- Reason code.
- Optional user-facing clarification question.

The model must never set the current user's permissions or choose an arbitrary database connection.

## 9.6 Prompt/context construction

The final SLM context should include:

1. System instructions and output contract.
2. User's question.
3. Relevant conversation state.
4. Approved domain.
5. Selected business definitions.
6. Relevant metrics.
7. Required columns.
8. Verified relationships.
9. Temporal and grain constraints.
10. Approved output schema.

The order should be stable and tested.

## 9.7 Token efficiency

We should keep ordinary prompts compact and measure their actual size using the model tokenizer.

Recommended optimization principles:

- Include only selected tables and columns.
- Avoid repeating descriptions.
- Do not send all historical chat messages.
- Prefer structured metadata over verbose prose where appropriate.
- Avoid sending raw database records to the model by default.
- Avoid unnecessary examples.
- Use compact structured output.
- Cache immutable metadata preparations.
- Avoid generating explanatory reasoning text when the task only requires a query plan.

Do not enforce a context budget that excludes mandatory business rules.

## 9.8 Model decoding settings

Start with deterministic or low-temperature decoding for query planning.

Use constrained structured output where supported by the selected runtime.

Model output limits, repetition controls and timeout policies should be calibrated experimentally.

## 9.9 Model failure conditions

Possible failures:

- Invalid JSON.
- Missing required fields.
- Hallucinated metric ID.
- Invalid filter operator.
- Truncated output.
- Model timeout.
- Unavailable inference server.
- Ambiguous result.

All must have defined error handling.

No invalid plan can reach database execution.

---
