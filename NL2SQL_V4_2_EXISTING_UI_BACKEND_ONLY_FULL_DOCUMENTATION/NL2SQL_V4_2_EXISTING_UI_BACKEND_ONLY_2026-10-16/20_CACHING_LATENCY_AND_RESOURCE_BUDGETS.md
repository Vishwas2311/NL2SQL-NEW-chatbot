# 20 — Caching, Adaptive Retrieval, Token and Latency Budgets

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Draft for review; no implementation or company production validation performed.  
**Document owner:** Platform + ML + backend  
**Gate:** P0/P1  
**Baseline reference:** V4 research/blueprint supplied on 2026-10-15.  
**Data policy:** Fictional examples only; actual company schema and customer data stay in approved office systems.

> **Core distinction:** this document specifies future behavior. It does not claim that these modules, controls, model benchmarks, or Oracle permissions are already deployed.

## Design specification

## Performance rule
Optimize end-to-end p50/p95, correctness and cost together. A fast query that returns the wrong business result is not an improvement. Every request has a deadline budget spanning authentication, retrieval, model, compilation, Oracle and formatting. Initial budget values are **configuration placeholders** to be measured on target hardware, not universal targets.

## Cache matrix
| Cache | Scope/key | Default |
|---|---|---|
| Catalog and graph | Immutable `catalog_version` + policy version | Enabled |
| BM25/index | Catalog and approved view of metadata | Enabled |
| Embedding index | Model embedding digest + catalog version | Conditional |
| Join paths | Metric/dimension/period class + catalog/policy digest | Enabled with bounds |
| Certified template match | Authorized scope + catalog version + normalized slots | Conditional |
| SLM stable prefix | Model/runtime + approved prompt version | Runtime-dependent |
| Oracle query result | User/tenant authorization + binds + data freshness | Disabled pending approval |

## Latency event schema
Record spans `auth_ms`, `session_ms`, `lexical_ms`, `vector_ms`, `graph_ms`, `context_ms`, `prefill_ms`, `decode_ms`, `compile_ms`, `validate_ms`, `preflight_ms`, `oracle_ms`, `format_ms`. Also record `input_tokens`, `output_tokens`, `slm_calls`, `retry_count`, `catalog_version`, model/runtime version and cache hit indicators. Sensitive values should be suppressed or hashed with appropriate controls.

## Model optimization path
Prefer 0 SLM calls for strict certified templates; typically 1 planning call for supported natural language; permit bounded fallback only if needed. Keep exact/BM25 first but allow vector retrieval on low coverage or validated paraphrase cases. Use minimum complete context, stable prompt prefix, correct tokenizer counting, output JSON schema, appropriately sized KV/context memory, and explicit admission control for GPU concurrency.

## Oracle protection
Pool size, read-only resource plans, per-user rate limits, concurrent query semaphore, timeout and response bytes limit. Query preflight rejects predicted resource overrun where information is available. Never allow automatic repeated execution on transient timeouts without safe idempotency controls.

## Experiment design
Benchmark at least lexical-only, lexical+embeddings, direct-SLM-SQL, graph-grounded-SLM-SQL, compiler-first; hold fixtures/model constant. Record accuracy AND coverage AND p95. If vector search or cache introduces inconsistency, roll back regardless of small p50 gains.



## V4.1 performance gate and caching by view version
Latency budget must span authenticated request → return, with child spans for lexical, optional vector, join/path, value-resolution, SLM prefill/decode, plan/compile, SQL validation, preflight, Oracle execution and formatting. Zero-SLM fast path is not necessarily cheap if Oracle query execution is costly. No hard-coded ms target is assumed until approved workload measurements.
Cache keys need catalog/view version, policy digest, principal/tenant scope, SQL template/plan version, model/provider version where model-affecting, temporal parameters and source freshness. Metadata, index and join graph can be precompiled; result caches remain disabled by default unless DB-level auth and freshness semantics are approved. Use concurrency admission control and a single absolute request deadline for all substeps.
Track **end-to-end speed and actual business answer accuracy together**, including vector inference overhead and p95 tail effects. See [32](./32_RETRIEVAL_TECH_CHOICES_AND_EXPERIMENTS.md).

---

## Deliverables / artifacts to review

Span definitions, provisional budget config, cache-key/invalidation policy, ablation benchmarks

## Acceptance tests and exit criteria

No scope-leaking caches; predictable deadline handling; benchmark p50/p95 and all retries under concurrency

## Open decisions and evidence required

Expected request volume, latency SLO, inference hardware, data freshness TTL, peak connections?

## Related documents

[03](./03_SYSTEM_ARCHITECTURE_AND_RUNTIME.md), [06](./06_RETRIEVAL_LEXICAL_VECTOR_AND_RANKING.md), [09](./09_ROUTING_CONFIDENCE_AND_EXECUTION_PATHS.md), [11](./11_LOCAL_SLM_MODEL_CONTEXT_AND_RUNTIME.md), [15](./15_ORACLE_ADAPTER_PREFLIGHT_AND_RESOURCES.md), [19](./19_RESULT_PROVENANCE_FRESHNESS_AND_EXPLANATIONS.md), [22](./22_PRIVATE_DEPLOYMENT_INFRA_AND_FULCRUM.md), [23](./23_OBSERVABILITY_SRE_AND_OPERATIONS.md), [24](./24_TEST_DATA_EVALUATION_AND_BENCHMARKS.md)


---

## Configurable budget schema (illustrative fields, not approved numeric values)
```yaml
request:
  end_to_end_deadline_ms: TO_BE_MEASURED
  max_repair_attempts: 1
  max_clarifications_per_request: TO_BE_APPROVED
model:
  prompt_token_budget: BENCHMARK_DEPENDENT
  output_token_budget: BENCHMARK_DEPENDENT
  max_concurrent_inference: HARDWARE_DEPENDENT
oracle:
  max_returned_rows: DBA_APPROVED
  statement_timeout_ms: DBA_APPROVED
  max_concurrent_queries: DBA_APPROVED
```
Store actual numbers in versioned, validated configuration, not scattered magic constants. A deadline request passes remaining time budget downstream. If model planning overruns, do not give the resulting SQL unlimited Oracle time.

## Performance experiment protocol
Use a fixed hardware/model snapshot and 150-case golden set; warm versus cold starts reported separately. Measure baseline lexical retrieval, vector-assisted retrieval, graph + compiler, strict template fast path, complex fallback. Report p50 and p95 alongside business-result accuracy/coverage, not throughput alone. Exclude model cold-load time only if the production service preloads and monitors readiness. Quantify GPU queue wait and Oracle pool acquisition time separately.

---

## Historical V4 Baseline Requirements (reference only; superseded where V4.1 refines them)

> **Historical UI exclusion:** Any older requirement below to create a React/TypeScript/Vite frontend, new browser pages, screens, or UI build/test pipeline is superseded by the user decision. These are historical notes, **not implementation tasks**. Preserve existing capabilities for later integration via document 35.

> This is preserved from the earlier planning draft for comparison. The current V4.1 design section, companion docs 30–34, the approved ADR register, and subsequent validated contracts take precedence on changes explicitly addressed in the V4.1 refinement. Historical descriptions of optional vector providers, open SQL fallback, and late Oracle tests are **not** new mandatory decisions.


The following material records relevant requirements from the previously agreed V4 blueprint. The sections above are the detailed module design and take precedence where they add stricter controls. Original V4 is a **proposed architecture**, not independently verified production source.

# 19. Caching Strategy

Caching should reduce repeated work without violating access controls.

## 19.1 Cache candidates

| Cache | Purpose |
|---|---|
| Metadata snapshot | Avoid repeated file/database metadata reads |
| Keyword index | Fast local matching |
| Embedding index | Avoid repeated metadata embedding |
| Join-path cache | Reuse verified graph paths |
| Query-plan template cache | Skip model inference for certified patterns |
| Prompt-prefix cache | Reuse stable model context where runtime supports it |
| Result cache | Optional, for approved stable queries |

## 19.2 Cache keys

Cache entries must account for relevant factors such as:

- Catalog version.
- User authorization scope.
- Tenant/security context.
- Business parameters.
- Reporting period.
- Data freshness rules.
- Compiler version.

Never reuse a privileged user's result for another user merely because the SQL is identical.

## 19.3 Cache invalidation

Invalidate affected entries when:

- Semantic definitions change.
- Permissions change.
- Metadata versions change.
- Business query rules change.
- Data freshness thresholds expire.

For the initial release, avoid result caching unless the authorization and freshness model is sufficiently mature.

---

---

# 22. Observability and Performance Monitoring

We should be able to explain the time consumed by each request.

## 22.1 Request tracing

Track stages including:

1. Authentication.
2. Session loading.
3. Intent routing.
4. Retrieval.
5. Graph resolution.
6. Context preparation.
7. SLM inference.
8. Query-plan validation.
9. SQL compilation.
10. SQL validation.
11. Oracle execution.
12. Result formatting.
13. Response delivery.

## 22.2 Model metrics

Track:

- Prompt tokens.
- Generated tokens.
- Time to first token.
- Total inference time.
- Model loading time.
- Inference concurrency.
- Peak memory usage.
- Structured output failures.
- Repair attempts.

## 22.3 SQL metrics

Track:

- Query compilation success rate.
- Oracle execution success rate.
- Validation rejection categories.
- Join validation failures.
- Business semantic errors.
- Database execution time.
- Timeouts.
- Result truncations.

## 22.4 Operational metrics

Track:

- End-to-end latency.
- p50 and p95 response time.
- Requests per minute.
- Active sessions.
- Concurrent queries.
- Cache hit rate.
- CPU/GPU/memory utilization.
- Metadata version.
- Model version.
- Failure rate.

Do not record sensitive query values or raw customer data in ordinary telemetry.

## 22.5 Performance optimization order

Optimize in this sequence:

1. Eliminate unnecessary SLM calls.
2. Reduce excessive context.
3. Cache approved metadata.
4. Avoid repeated embeddings.
5. Use efficient lexical and graph lookups.
6. Optimize model/runtime settings.
7. Optimize SQL compilation and database execution.
8. Improve concurrency and connection pooling.
9. Consider additional infrastructure only when justified.

A faster model cannot compensate for a slow Oracle query or repeated unnecessary database operations.

---
