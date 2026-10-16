# 32 — Retrieval, Embeddings, Graph Technology Choices and Promotion Experiments

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Proposed baseline with optional upgrades gated on measured benefit. **Owners:** Search/AI engineer + QA + security/platform. No benchmark result is asserted.

## Why retrieval is separate from Gemma
A 12B SLM can identify tables from a full schema, but processing irrelevant columns increases prompt size and the chances of selecting the wrong source. Dedicated retrieval has overhead and may miss correct fields. Neither approach should be treated as universally better. For our relatively small *reported* office schema inventory, a compact scoped catalog + Gemma direct baseline is mandatory in benchmarks.

## Selected local baseline
1. Authorization/tenant filter **before** any ranking or logging of candidates.
2. Normalize exact metric/entity IDs, approved synonyms and acronyms.
3. Embedded SQLite FTS5 with `bm25()` over approved *metadata text*; use a portable provider interface if the company forbids embedded SQLite.
4. Verify the requested metric/view/domain, expand to all necessary join keys, temporal and policy rules from the certified catalog graph.
5. If grounding incomplete, either ask for clarification or *conditionally* run the optional vector arm if it has been promoted for the domain.
6. Return a provenance-rich `GroundingBundle` of stable approved IDs, not loose SQL DDL or untrusted raw customer rows.

## Optional vector arm
- Local encoder checkpoint selected through authorized model/license/privacy evaluation; record dimensions, embedding normalization, text preprocessing and version.
- FAISS CPU as the initially preferred embedded vector-search *library* with reproducible index build and publication digest. **Feature flag OFF by default** until held-out evaluation justifies it.
- No required hosted vector database. Milvus/Qdrant are future adapters only if concurrency/index lifecycle/size or corporate standards require them.
- No raw customer/entity values or private samples in metadata embeddings by default. Secure entity lookup is Document 08.
- Rank vectors only within the principal's approved metadata scope. If a global ANN index cannot guarantee filtering before candidates are exposed, prepartition indexes by authorized scope or post-filter with protected index access and leakage tests; do not leak candidate names through diagnostics.

## Graph choice
**NetworkX in-memory** graph of certified physical relationships, loaded from the same catalog at startup with immutable snapshot version. It is *not* a separate Neo4j/Graphify graph DB. If performance or package restrictions require it, a custom typed adjacency map can replace NetworkX behind an identical `JoinResolver` port. The catalog certifies edges; NetworkX does not.

## Reproducible A–G benchmark
| Run | Candidate architecture | Isolated hypothesis |
|---|---|---|
| A | Small scoped catalog → direct Gemma SQL | Is retrieval needed at all? |
| B | Exact + FTS5/BM25 → Gemma SQL | Value of lexical schema grounding |
| C | B + local FAISS retrieval → Gemma SQL | Value of embeddings independent of compiler |
| D | B + verified graph → Gemma SQL | Value of physical join evidence |
| E | B + typed Gemma plan + deterministic compiler | Value of controlled SQL generation |
| F | E + governed views | Value/cost of view abstraction |
| G | F + optional promoted FAISS on incomplete grounding | Value/cost of adaptive retrieval |
**Fair comparison:** Same synthetic fixtures, semantic definitions, principal, SLM checkpoint/runtime/hardware, schema/catalog digest, request timeout and task mix. Change only the indicated dimension; report medians and tail latencies along with answer accuracy and supported-question coverage. Some runs may not have identical execution ability; distinguish unavailable from incorrect.

## Required scoring
- Correct metric/domain/table/column recall at k and complete physical-join dependency coverage.
- Business result accuracy on all valid questions and on answered-only questions; coverage and clarification correctness reported separately.
- Hallucinated/unapproved schema ID rate and **zero unauthorized execution** hard gate.
- SLM calls, input/output tokens, local encoder CPU/RAM overhead, index size/startup, end-to-end p50/p95, Oracle execution time/concurrency.
- Retrieval consistency for exact aliases, paraphrases, unfamiliar terms, table-first and column-first questions, near-duplicate descriptions, and time-role ambiguities.

## Promotion rule (no invented score)
The QA/product/platform owners agree quantitative min-gain and max-regression thresholds **before** benchmarking. Promote FAISS per domain only if relevant accuracy/coverage gains beat measured overhead and no policy leakage occurs. Disable immediately on regression. Do not promote merely because cosine score seems high or 'best model' is advertised. Revalidate whenever metadata/index/model version changes.

## Deliverables
Machine-readable benchmark cases and predicted selections, reproducible run manifest with model/index digests, scorecard across A–G, selection ADR and rollback condition. Cross-reference 06/07/09/11/20/24/28.
