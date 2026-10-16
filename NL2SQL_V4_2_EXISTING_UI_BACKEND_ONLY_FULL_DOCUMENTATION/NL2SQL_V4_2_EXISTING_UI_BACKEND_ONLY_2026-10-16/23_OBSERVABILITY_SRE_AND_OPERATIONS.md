# 23 — Observability, SRE Runbooks, Audit and Reliability

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Draft for review; no implementation or company production validation performed.  
**Document owner:** SRE + backend/ML operations  
**Gate:** P0  
**Baseline reference:** V4 research/blueprint supplied on 2026-10-15.  
**Data policy:** Fictional examples only; actual company schema and customer data stay in approved office systems.

> **Core distinction:** this document specifies future behavior. It does not claim that these modules, controls, model benchmarks, or Oracle permissions are already deployed.

## Design specification

## Telemetry policy
Every request produces one trace ID and spans for auth, session, exact/BM25, embedding, graph, context, model prefill/decode, plan validation, compilation, SQL AST checks, Oracle preflight, Oracle execution and formatting. Record stage durations, safe counts and version identifiers. Do not log full prompts, customer filter values, raw results or privileged schema text by default.

## Domain correctness signals
Besides 5xx, monitor `UNSUPPORTED`, `CLARIFICATION_REQUIRED`, `METRIC_UNCERTIFIED`, `JOIN_AMBIGUOUS`, `INVALID_OUTPUT`, `SQL_DENIED`, `ORA_TIMEOUT`, `DATA_STALE`, `RESULT_TRUNCATED`. Track accuracy via labeled feedback review and test replay; a high SQL execution success rate alone can hide wrong business answers.

## SLO candidates for signoff
Availability of chat API; authorized query success rate; p50/p95 end-to-end latency for fast/normal/complex paths; inference capacity and queue wait; Oracle query timeout rate; verified metric coverage; privacy and safety invariants. Do not publish concrete promises before load tests on target infrastructure.

## Runbooks
Model endpoint down; Oracle pool exhausted; catalog version mismatch; metadata publication rollback; query cost spike; drift alert; SLM JSON parser failure increase; vector index unavailable; session DB unavailable; audit exporter outage; suspected unauthorized disclosure. Every runbook states symptom, detection, safe degraded behavior, owner, rollback action and incident escalation.

## Release health
Canary rollout with synthetic regression and approved office golden checks, no security regression, validated catalog snapshot, structured dashboards and tested rollback. Significant errors in auth, policy or query correctness trigger kill-switch for SQL execution, not only model provider switching.



## V4.1 observability: accuracy, coverage and route evidence
Track `semantic_view_id/version` in restricted audit telemetry, never reveal restricted physical source identifiers to clients. Aggregate metrics: route shares (`template`, `compiler`, `guarded_fallback`, `clarify`, `deny`, `unsupported`), entity resolution ambiguity, retrieval recall by arm, join/grain rejection, SQL dialect incompatibility, preflight cost/timeout, result freshness unknown/stale and user feedback type. Correlate trace identifiers across model request, compiler proof, DB preflight and response; redact sensitive values and query literals.
A release must declare both *correct-result accuracy* and *valid-question coverage* (including unsupported rates), plus safety escape count and p95 latency. Alerts should distinguish rising unsupported-query coverage from actual model/service outages. Model/runtime change requires canary comparisons with pinned catalog/view versions.

---

## Deliverables / artifacts to review

Event/spans schema, dashboards, alert thresholds proposal, incident runbooks, canary release gate

## Acceptance tests and exit criteria

Failure simulations with safe degradation; redacted tracing; no execution on invalid snapshot or policy

## Open decisions and evidence required

Which observability platform and retention? Who handles after-hours alerts?

## Related documents

[03](./03_SYSTEM_ARCHITECTURE_AND_RUNTIME.md), [19](./19_RESULT_PROVENANCE_FRESHNESS_AND_EXPLANATIONS.md), [20](./20_CACHING_LATENCY_AND_RESOURCE_BUDGETS.md), [21](./21_SECURITY_PRIVACY_THREAT_MODEL.md), [22](./22_PRIVATE_DEPLOYMENT_INFRA_AND_FULCRUM.md), [24](./24_TEST_DATA_EVALUATION_AND_BENCHMARKS.md), [25](./25_IMPLEMENTATION_ROADMAP_DEPENDENCIES_AND_GATES.md)


---

## Sample alert routing and runbook entry
**Alert:** `catalog_index_mismatch > 0`. **Impact:** Retrieval could use stale metadata. **Automatic action:** stop all natural-language query execution; keep health endpoint reporting not-ready, optionally allow admin diagnostics. **Owner:** catalog/data engineering on call. **Recovery:** verify signed active catalog, rebuild matching index bundle, replay synthetic smoke suite, only then enable traffic. **Evidence:** trace ID, version mismatch digests and successful recovery test—no customer rows in logs.

**Alert:** `oracle_timeout_rate` spikes. **Action:** reduce permitted concurrency, inspect DBA workload from approved tooling, identify query classes, temporarily disable complex fallback if needed. Do not retry heavy SQL automatically and worsen overload.

**Alert:** `llm_invalid_plan_rate` spikes after new model rollout. **Action:** compare model artifact and prompt schema version, roll back model adapter, restore stable provider; no relaxation of plan validator.

### Monitoring dimensions
Environment, public API version, model ID/runtime, catalog digest, semantic domain and route class; user identity should not be a routine metrics label. Use protected audit references if user-level investigation is authorized.

---

## On-call fault-to-action matrix
| Symptom | Immediate containment | Owner | Evidence |
|---|---|---|---|
| Unauthorized SQL validator bypass alert | Disable query execution, isolate affected build | Security/backend | Query trace, validator capability IDs |
| Model invalid JSON spike | Roll back model/prompt, keep validator enforced | ML/platform | Output error counts/model revision |
| Wrong certified metric after catalog update | Revert published catalog pointer, invalidate caches | Data steward | Catalog digests/golden failures |
| Oracle p95 timeout spike | Restrict query concurrency and complex fallback | DBA/SRE | Pool wait, preflight, DB execution spans |
| Value enumeration attempts | Rate-limit resolver, review incident | Security | Anonymized denied lookup counters |
| Catalog/vector digest mismatch | Prevent ungrounded requests until index rebuilt | Catalog owner | Version report |

### Correctness monitoring process
Users can flag an answer via a query reference. An authorized reviewer can compare the protected execution manifest against the domain goldens, categorize issue (wrong term, alias, join, grain, date, compiler, model, DB freshness, presentation) and create a regression test with synthetic reproduction. Never automatically use flagged production SQL/rows as model-training data.

### Operations drills
At least once per release candidate rehearse model server unavailability, Oracle pool exhaustion, network TLS rotation, catalog rollback, expired auth and permission change mid-session. A “green” health endpoint alone does not establish permission or answer correctness; readiness includes critical dependencies and safe fail-closed behavior.

---


## V4.2 Existing UI integration telemetry boundary
Backend traces and logs must label legacy EWS compatibility route latency and errors, without copying transcript audio, customer literals, SQL text or browser bearer tokens into telemetry. UI smoke tests and browser RUM are deferred until authorized later integration; this phase measures synthetic API response correctness/latency and secured session ownership. See [35](./35_EXISTING_UI_INTEGRATION_CONTRACT.md).

---

## Historical V4 Baseline Requirements (reference only; superseded where V4.1 refines them)

> **Historical UI exclusion:** Any older requirement below to create a React/TypeScript/Vite frontend, new browser pages, screens, or UI build/test pipeline is superseded by the user decision. These are historical notes, **not implementation tasks**. Preserve existing capabilities for later integration via document 35.

> This is preserved from the earlier planning draft for comparison. The current V4.1 design section, companion docs 30–34, the approved ADR register, and subsequent validated contracts take precedence on changes explicitly addressed in the V4.1 refinement. Historical descriptions of optional vector providers, open SQL fallback, and late Oracle tests are **not** new mandatory decisions.


The following material records relevant requirements from the previously agreed V4 blueprint. The sections above are the detailed module design and take precedence where they add stricter controls. Original V4 is a **proposed architecture**, not independently verified production source.

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
