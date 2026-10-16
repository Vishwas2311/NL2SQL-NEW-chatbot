# 24 — Synthetic Golden Data, Evaluation, Ablations and Quality Metrics

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Draft for review; no implementation or company production validation performed.  
**Document owner:** QA/AI + DBA + product  
**Gate:** P0  
**Baseline reference:** V4 research/blueprint supplied on 2026-10-15.  
**Data policy:** Fictional examples only; actual company schema and customer data stay in approved office systems.

> **Core distinction:** this document specifies future behavior. It does not claim that these modules, controls, model benchmarks, or Oracle permissions are already deployed.

## Design specification

## Evaluation charter
Architectural quality must be measured, not declared. Compare v2-style direct SQL, v3-style graph grounding and v4 compiler-first using the same synthetic catalog, questions, authorizations and correct expected result sets. Then validate with an approved office-only Oracle benchmark corpus. Public text-to-SQL accuracy is contextual background, not a local deployment prediction.

## Reproducible synthetic fixture set
Include one-to-one, one-to-many, many-to-many, composite joins; cancelled/refunded statuses; currency variations; rounding; nulls; duplicated natural identifiers; historical effective-date overlap; quarterly/fiscal boundaries; access-restricted rows; known expensive queries and denied tables. Seed generator deterministic, data and golden expected rows versioned. Never use real customer examples in portable fixtures.

## 150-case proposed launch suite (expand with owners)
| Category | Cases | Purpose |
|---|---:|---|
| Lookup, filter, sort, limit | 20 | Basic plan/SQL correctness |
| Certified metric arithmetic and grouping | 25 | Business rules, units, null handling |
| Multi-table joins, fan-out and grain | 25 | Correct aggregation across sources |
| Temporal and historical/as-of | 20 | Effective dates/fiscal boundaries |
| Paraphrases, lexical/vector retrieval | 15 | Grounding coverage |
| Value resolver, ambiguous entity names | 15 | Secure matching/clarification |
| Follow-up and conversation state | 10 | Context fidelity |
| Complex SQL compiler fallback | 10 | Coverage and safety |
| Authorization, injection, resource denial | 10 | No unsafe execution |
| **Total** | **150** | Initial proposed corpus |

## Multi-layer scoring
Measure retrieval recall (tables/columns/metric), certified join edge coverage, normalized plan equivalence, compile success, SQL exec accuracy, **actual business-result accuracy**, supported valid-question coverage, correct clarification/abstention, p50/p95 duration, SLM calls/tokens and peak memory/concurrency. Distinguish parse-valid but semantically wrong SQL from safety rejection. Report result accuracy and coverage jointly; a compiler that refuses difficult valid questions must not appear artificially superior.

## Ablation suite
A=lexical+direct model SQL; B=lexical/vector+model SQL; C=verified graph+direct SQL; D=typed plan/compiler with lexical only; E=typed plan/compiler with optional vector; F=E plus value resolver/confidence/preflight. Compare on held-out categories with exact same device/model/settings. Record cost of each added component.

## Release gates
No unsafe Oracle execution in adversarial suite; approved metric and grain correctness; reproducible reports; explicit latency/coverage thresholds chosen after baseline; regression gate tied to CI and every catalog/model/compiler version. Oracle-only tests occur exclusively in approved internal environment.



## V4.1 mandatory architecture benchmark extension
Add a **paired, held-out suite** (same authorized principal, domain, model checkpoint, runtime/hardware, schema/view snapshot, time budget, Oracle fixtures) comparing:
| ID | Configuration | What it tests |
|---|---|---|
| A | Compact relevant catalog → Gemma SQL, no embeddings | Direct-model baseline, small schema |
| B | Exact + FTS5/BM25 → Gemma | Lexical value, no embedding |
| C | Exact + BM25 + local encoder/FAISS → Gemma | Vector marginal retrieval gain |
| D | Certified relationships and grain → Gemma SQL | Join-proof marginal gain |
| E | Certified catalog + typed plan + compiler | Compiler-first baseline |
| F | E + governed semantic views | View abstraction marginal gain |
| G | F + adaptive vector only when needed | Full target with selective retrieval |
Do **not** compare pure architecture scores with different model weights or different authorized data. Report metric/table/column retrieval recall, valid-question coverage, correct-result accuracy over *all eligible* requests and accepted-only, SQL syntax/execution success, join/grain truth, unauthorized execution zero-gate, clarification appropriateness, p50/p95, SLM calls/tokens, Oracle load and memory. Gate vector and semantic view promotion on predefined tradeoff tolerances rather than a single leaderboard score. Include counterexamples where views reduce coverage or create fan-out risks. See [32](./32_RETRIEVAL_TECH_CHOICES_AND_EXPERIMENTS.md).

---

## Deliverables / artifacts to review

Golden dataset schema, question list, expected outputs, benchmark script requirements, acceptance dashboard

## Acceptance tests and exit criteria

Expected result rows match for certified corpus; zero unsafe execute calls; reproducible config and disaggregated coverage

## Open decisions and evidence required

Who supplies office golden queries and approves true answers? What target throughput/accuracy?

## Related documents

[04](./04_SEMANTIC_CATALOG_AND_GOVERNANCE.md), [06](./06_RETRIEVAL_LEXICAL_VECTOR_AND_RANKING.md), [07](./07_JOIN_GRAPH_GRAIN_AND_TEMPORAL_RULES.md), [08](./08_ENTITY_AND_VALUE_RESOLUTION.md), [09](./09_ROUTING_CONFIDENCE_AND_EXECUTION_PATHS.md), [10](./10_QUERY_PLAN_DSL_AND_VALIDATION.md), [12](./12_DETERMINISTIC_SQL_COMPILER_AND_TEMPLATES.md), [13](./13_COMPLEX_SQL_FALLBACK_AND_REPAIR.md), [14](./14_SQL_VALIDATION_POLICY_AND_SECURITY.md), [15](./15_ORACLE_ADAPTER_PREFLIGHT_AND_RESOURCES.md), [20](./20_CACHING_LATENCY_AND_RESOURCE_BUDGETS.md), [25](./25_IMPLEMENTATION_ROADMAP_DEPENDENCIES_AND_GATES.md)


---

## Test-case record schema
```yaml
id: SYN-AGG-017
question: "Show 2025 completed-order net sales by region"
user_role: analyst
catalog_version: demo-v1
expected_route: normal
expected_metric_ids: [net_sales]
expected_join_edge_ids: [orders_to_customer, customer_to_region]
expected_grain: [region]
expected_result_fixture: expected/SYN-AGG-017.json
expected_status: completed
must_not_reference: [payments]
```
Write expected result fixtures independently of model output and SQL compiler; otherwise tests would merely verify the system agrees with itself. For each case record acceptable clarification decisions, required public provenance fields and forbidden disclosures.

### Holdout methodology
Split canonical question templates and paraphrase groups so semantic twins do not leak from training/prompt examples into test set. Test historical edge dates and deliberate duplicate fan-out separately. Baseline and candidate must run against identical database snapshot, access policy and model settings. Report 95% confidence intervals for aggregate measures where sample size permits, but do not obscure mandatory zero-unsafe-execution conditions.

---


## V4.2 Pre-integration EWS compatibility tests
Add backend httpx/Pytest contract goldens for `/health`, `/ews-chatbot/chat`, `/ews-chatbot/get_all_sessions`, `/ews-chatbot/load_session/{id}`, `/ews-chatbot/delete_session/{id}` where supported, and optional STT endpoint. Include session isolation, fake browser `user_id` mismatch, token expiration, result rows as objects, missing optional SQL, read-only security and stable error behavior. No frontend render/build requirement before later UI integration. At approval time, use the unmodified UI reference files for browser smoke testing. See [35](./35_EXISTING_UI_INTEGRATION_CONTRACT.md).

---

## Historical V4 Baseline Requirements (reference only; superseded where V4.1 refines them)

> **Historical UI exclusion:** Any older requirement below to create a React/TypeScript/Vite frontend, new browser pages, screens, or UI build/test pipeline is superseded by the user decision. These are historical notes, **not implementation tasks**. Preserve existing capabilities for later integration via document 35.

> This is preserved from the earlier planning draft for comparison. The current V4.1 design section, companion docs 30–34, the approved ADR register, and subsequent validated contracts take precedence on changes explicitly addressed in the V4.1 refinement. Historical descriptions of optional vector providers, open SQL fallback, and late Oracle tests are **not** new mandatory decisions.


The following material records relevant requirements from the previously agreed V4 blueprint. The sections above are the detailed module design and take precedence where they add stricter controls. Original V4 is a **proposed architecture**, not independently verified production source.

# 23. Testing and Evaluation Strategy

We must prove correctness, efficiency and security independently.

## 23.1 Test levels

**Unit tests**

- Semantic definitions.
- Metadata import.
- Retrieval ranking.
- Join-path resolution.
- Plan validation.
- SQL compilation.
- SQL validation.
- Permission logic.

**Integration tests**

- FastAPI and session storage.
- Mock SLM adapter.
- Retrieval and compiler.
- Database adapters.
- Frontend and API contracts.

**End-to-end tests**

- Natural language question.
- Generated query plan.
- SQL generation.
- Database execution.
- Final answer.

**Security tests**

- Unsafe SQL.
- Unauthorized data access.
- Injection attempts.
- Session isolation.
- Permission-aware caching.

**Performance tests**

- SLM latency.
- Retrieval latency.
- Concurrent requests.
- Long conversations.
- Resource utilization.

## 23.2 Golden question suite

Create an initial synthetic evaluation suite of at least 100 representative questions.

Suggested categories:

| Category | Suggested count |
|---|---:|
| Basic lookups | 10 |
| Aggregation and totals | 15 |
| Filters and sorting | 10 |
| Multi-table joins | 15 |
| Historical/time queries | 15 |
| Business metric calculations | 10 |
| Complex analytic questions | 10 |
| Ambiguous/unsupported questions | 10 |
| Security and denial cases | 5 |
| **Total** | **100** |

Expand it as new behaviors are implemented.

For enterprise validation, use approximately 200–300 approved representative business questions as an initial test-design target, subject to availability.

## 23.3 Required evaluation measurements

| Metric | What we measure |
|---|---|
| Table retrieval recall | Whether all required tables were retrieved |
| Column retrieval recall | Whether required columns were retrieved |
| Join accuracy | Whether joins follow approved relationships |
| Metric correctness | Whether business formulas are respected |
| SQL execution accuracy | Whether SQL executes successfully |
| Business-result accuracy | Whether the returned answer is actually correct |
| Coverage | Percentage of questions the system can answer |
| Safe rejection | Correct refusal or clarification of unsupported requests |
| Median latency | Typical response performance |
| p95 latency | Slower end-user experience |
| Model token usage | Average prompt and output tokens |
| Model calls | SLM invocations per question |
| Memory utilization | Runtime feasibility |
| Concurrency | Behavior under multiple active users |

## 23.4 Architecture comparisons

Run the same evaluation dataset against:

**Baseline A:** Hybrid retrieval + Gemma direct SQL generation.

**Baseline B:** Hybrid retrieval + verified join graph + Gemma SQL generation.

**Target C:** Governed semantic catalog + structured plans + deterministic compiler + restricted fallback.

We will compare actual results.

We should not claim the proposed architecture is faster or more accurate until the tests confirm it.

## 23.5 Model comparisons

Use the same retrieval engine, metadata, query compiler and evaluator when comparing SLMs.

Only change the model provider.

This ensures that apparent model improvements are not caused by unrelated pipeline changes.

## 23.6 Acceptance principles

Mandatory release conditions:

- No unauthorized SQL execution in the security suite.
- No unsupported business definition silently invented.
- Certified query templates produce validated expected results.
- Catalog and compiler version consistency.
- Full session isolation.
- All mandatory API compatibility tests pass.
- Oracle permission and dialect tests pass in the approved environment.

Accuracy, latency and coverage thresholds should be agreed on based on measured benchmarks and business criticality.

High correctness on only a small subset of questions is not sufficient. Coverage must also be reported.

---
