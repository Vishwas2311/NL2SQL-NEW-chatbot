# 06 — Permission-Aware Retrieval, Keyword Search and Optional Vectors

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Draft for review; no implementation or company production validation performed.  
**Document owner:** AI search engineering  
**Gate:** P0/P1  
**Baseline reference:** V4 research/blueprint supplied on 2026-10-15.  
**Data policy:** Fictional examples only; actual company schema and customer data stay in approved office systems.

> **Core distinction:** this document specifies future behavior. It does not claim that these modules, controls, model benchmarks, or Oracle permissions are already deployed.

## Design specification

## Core rule
Retrieval returns candidates with provenance; it does not certify table legitimacy, metric correctness or join validity. The principal's entitlements filter candidate sets **before** lexical or vector matching to prevent disclosure through candidate names, synonyms and ranking results.

## Baseline and upgrade sequence
Start with exact identifier/alias matching, normalized acronym expansion, token search and BM25 against compact descriptions. Only add embeddings when a held-out paraphrase suite shows improvement. Because source inventory suggests a limited number of tables, full local candidate scoring may be adequate. Do not require Milvus/Qdrant services as day-one architecture.

## Retriever contract
`retrieve(principal, intent, slots, catalog_version, k, budget) -> GroundingCandidates`: list of stable metric/table/column IDs, matched fields, lexical/semantic scores, source provenance, permission evidence, missing dependencies and evidence for clarification. Scores are rank signals, **not calibrated correctness probabilities**.

## Fusion and ambiguity
Resolve exact certified metric names before fuzzy candidates. If lexical and embedding arms disagree, evaluate business-domain scope, certified aliases and required fields; never silently choose a high cosine score. RRF may be benchmarked, but thresholding must be calibrated on approved development questions. Do not vector-search real customer names in metadata retrieval; entity values use document 08.

## Completeness and bounded expansion
Initial k is a tunable parameter. Expand graph neighbors only to supply needed joins/mandatory metric dependencies. A retrieved table without a legitimate path is discarded or triggers clarification. Context pruning must not drop join predicates, permission conditions, metric filters or time rules, even to meet token budgets.

## Diagnostics
Emit trace-safe counts: exact hits, lexical hits, vector hits, candidate fusion results, rejected unauthorized candidates, graph dependencies and final selected IDs. Avoid raw restricted labels in logs. Report recall@K, MRR, candidate churn, correct-metric recall and context token count for lexical-only versus lexical+vector ablations.

## Fallback philosophy
If vector engine unavailable, use exact/BM25 only when confidence criteria and required metadata allow; otherwise clarify or reject. Failure of a convenience retrieval feature must never disable core security checks.



## V4.1 fixed baseline, optional vector decision and experiment requirements
**Default:** principal/tenant entitlement filter → normalized exact match (IDs, certified metric aliases) → SQLite FTS5 `bm25()` for catalog descriptions/synonyms (or company-approved equivalent) → domain/view mapping resolution → missing-dependency expansion via verified graph. This is a *technology recommendation* awaiting enterprise package approval; not a claim that SQLite must hold production customer data. Never index customer rows in metadata FTS/vector by default.
**Optional:** local embedding model and FAISS CPU index, both private and snapshot-versioned, switched on only if held-out evaluation improves correct business-result coverage or retrieval recall without unacceptable p95 latency, memory or authorization failures. FAISS is a library, not a mandatory separate DB. Keep the encoder checkpoint, tokenizer, vector dimension/normalization and index build version in metadata; if vector service fails, continue lexical only if coverage proof remains complete.
**Ablations:** (1) scoped catalog + compact Gemma no embedding; (2) exact + FTS5/BM25; (3) exact + FTS5/BM25 + local embedding/FAISS; (4) table-first vs column-first retrieval; (5) with vs without semantic views/graph completion. Use the same goldens/model/hardware/time budgets; report metric/table/column recall, join completeness, *business-result accuracy*, supported valid-question coverage, p50/p95, tokens, and security denials. Do not use fixed cosine cutoffs as confidence probabilities. See [32](./32_RETRIEVAL_TECH_CHOICES_AND_EXPERIMENTS.md).

---

## Deliverables / artifacts to review

Lexical index, vector-provider interface, fusion scorer, calibrated retrieval tests, trace metrics

## Acceptance tests and exit criteria

Exact and paraphrase retrieval; denied catalog objects never surfaced; no missing join dependencies; lexical-only baseline

## Open decisions and evidence required

What is domain synonym coverage? Approved internal embedding model? Measured benefit threshold for installing vectors?

## Related documents

[04](./04_SEMANTIC_CATALOG_AND_GOVERNANCE.md), [05](./05_METADATA_INGESTION_AND_RECONCILIATION.md), [07](./07_JOIN_GRAPH_GRAIN_AND_TEMPORAL_RULES.md), [08](./08_ENTITY_AND_VALUE_RESOLUTION.md), [09](./09_ROUTING_CONFIDENCE_AND_EXECUTION_PATHS.md), [24](./24_TEST_DATA_EVALUATION_AND_BENCHMARKS.md)


---

## Candidate scoring and decision policies
Avoid inventing a single magic relevance score. Track separate signals: exact certified metric match, normalized synonym match, BM25 rank, embedding cosine (when enabled), domain compatibility, source mapping completeness, permission grants and relationship coverage. Hard violations (`unauthorized`, `uncertified metric`, `missing required table`) eliminate a candidate regardless of retrieval score. Maintain top-K only after security filtering.

**Example lexical test:** “show revenue for customers by month” must retrieve the approved revenue metric, its date dimension, relevant customer grouping and all required key fields. “turnover” may require synonym dictionary or approved embedding retrieval. “secret payroll data” must not reveal existence or ranking of denied objects. A misleading description planted in metadata must never expand grants.

**Vector ablation:** On held-out paraphrases, compare lexical-only recall/latency, local embedding-assisted recall/latency, and hybrid with join expansion. If vector improves recall but causes wrong certified-metric switches, favor safer calibration or clarification. Materialize per-metric aliases and examples during offline catalog build rather than embedding full long table descriptions repeatedly.

**Index publish:** `IndexBundle {catalog_hash, synonym_version, lexical_index_hash, embedding_model_id?, vector_index_hash?, build_time}`. Runtime refuses an index whose catalog hash differs from the request's snapshot. If a vector index is unavailable, lexical retrieval remains possible only when approved semantic coverage is complete.

---

## Historical V4 Baseline Requirements (reference only; superseded where V4.1 refines them)

> **Historical UI exclusion:** Any older requirement below to create a React/TypeScript/Vite frontend, new browser pages, screens, or UI build/test pipeline is superseded by the user decision. These are historical notes, **not implementation tasks**. Preserve existing capabilities for later integration via document 35.

> This is preserved from the earlier planning draft for comparison. The current V4.1 design section, companion docs 30–34, the approved ADR register, and subsequent validated contracts take precedence on changes explicitly addressed in the V4.1 refinement. Historical descriptions of optional vector providers, open SQL fallback, and late Oracle tests are **not** new mandatory decisions.


The following material records relevant requirements from the previously agreed V4 blueprint. The sections above are the detailed module design and take precedence where they add stricter controls. Original V4 is a **proposed architecture**, not independently verified production source.

# 6. Retrieval Engine — Finding Correct Tables and Columns

The retrieval engine finds relevant business definitions and schema objects.

It should not decide query correctness using similarity scores alone.

## 6.1 Recommended retrieval order

**Stage 1 — Permission filtering**

Determine which metadata is available to the authenticated user.

Unauthorized tables, columns or metrics must not be included in retrieved context.

**Stage 2 — Exact matching**

Search:

- Metric identifiers.
- Known business terms.
- Table aliases.
- Column aliases.
- Business synonyms.
- Abbreviations.
- Explicit identifiers.

**Stage 3 — Lexical retrieval**

Use BM25 or a similar keyword ranking method to find relevant metadata.

**Stage 4 — Conditional semantic retrieval**

Use local embeddings when exact and lexical retrieval cannot confidently resolve the wording, or when embedding-assisted retrieval has demonstrated value in evaluation.

**Stage 5 — Candidate fusion**

Combine relevant results from the available retrieval methods.

**Stage 6 — Relationship expansion**

Find required nearby objects and approved join paths.

**Stage 7 — Semantic reranking**

Prefer candidates with:

- Matching domain.
- Certified business definitions.
- Relevant metrics.
- Required columns.
- Valid physical relationships.
- Correct time rules.
- Sufficient authorization.

**Stage 8 — Context reduction**

Return only metadata required to answer the question.

## 6.2 Do we require a vector database?

No.

At the initial metadata scale, we should benchmark:

| Configuration | Purpose |
|---|---|
| Exact + BM25 | Fast, low-complexity baseline |
| Exact + BM25 + local embeddings | Measure improvement for synonyms and paraphrases |
| Hybrid + join resolution | Measure relationship correctness |
| Hybrid + model reranking | Use only if simpler ranking fails |

Use a local embedding index, such as FAISS or an approved embedded vector store, only when justified.

Do not introduce a second vector database for architectural appearance.

## 6.3 Retrieval output contract

The retrieval engine should return a structured object containing:

- User-question reference.
- Authorized domain.
- Selected metric IDs.
- Selected table IDs.
- Selected column IDs.
- Required relationship IDs.
- Required temporal rules.
- Relevant candidate scores.
- Catalog version.
- Provenance.
- Missing required definitions.
- Ambiguity information.

The model should not receive a raw, unbounded schema dump.

## 6.4 Retrieval failure

If no candidate has adequate grounding:

- Search approved synonyms and alternative matches.
- Request clarification if appropriate.
- Report the question as unsupported if necessary.

Never manufacture schema relationships because retrieval returned insufficient information.

---
