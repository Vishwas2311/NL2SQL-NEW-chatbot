# V4.1 Refined — Change Log and Evidence Register

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Release:** Pre-implementation design package, 2026-10-15.

## Compared with earlier v2/v3/V4 planning
- **New:** Dedicated secure entity/value resolver with authorized exact/alias lookup and bind-only filters.
- **Strengthened:** Intent confidence gate uses multi-signal verified completeness, not cosine score as a correctness probability.
- **Strengthened:** Oracle preflight and query resource protection, DB-enforced least privilege.
- **New dedicated contract:** Answer provenance and freshness distinguish data-as-of period, source refresh, and execution time.
- **Strengthened:** Office-only Oracle integration golden tests, independent from SQLite syntactic success.
- **Strengthened:** Configurable end-to-end performance budgets and auth-safe cache partitioning.
- **Strengthened:** Accuracy **and** answered-valid-question coverage, with ablation tests for vector/search/graph/compiler.
- **Preserved:** Compiler-first normal path, certified template fast path, bounded fallback, verified join graph and private inference.
- **Not required:** Graphify, Neo4j, dedicated vector servers, extra agent loops and fine-tuning.
- **UI decision updated in V4.2:** Sole user-supplied EWS HTML/CSS/JS UI; backend-only build now; EWS adapter required for later integration; no React replacement.

## Evidence classes
1. **User-provided v4 research and blueprint** (`Pasted text(20261015-162705).txt`, `Pasted text(20261015-170601).txt`): proposed design and references.
2. **Previous generated v2 plans:** planning baseline and component/test structure, not running application.
3. **Earlier Copilot screenshot/master spec:** reported office repository attributes and metadata counts; not an independent production runtime audit.
4. **This package:** newly authored architectural choices, risk controls and acceptance designs; none are empirical performance claims.

## Confidentiality boundary
The portable pack contains only invented business examples. Real schema data, customer values, Oracle credentials, internal addresses and proprietary Copilot output have not been copied into it. Actual integration and reconciliation occur only on approved company equipment/systems.

## Outstanding design/proof requirements
See document 26 and master index. A proposed component is not a deployed/verified component; architecture preference is not demonstrated accuracy or latency superiority.

## V4.1 refined design change log (2026-10-16)
This release was built from the 30 original numbered Markdown documents. It is a new proposal for owner review, not modified enterprise source code.
| Change | Impacted documents | Verification required |
|---|---|---|
| Governed semantic views and certified source/metric authority | 00–05, 07, 09–10, 12, 14, 16–19, 21, 24–28, 31 | Grain, source, policy and date-role goldens |
| Adaptive exact/BM25/vector search and table/column-first ablations | 03, 05–06, 09, 11, 20, 22–24, 28, 32 | Held-out recall, coverage, p95, memory |
| SQL fallback default disabled; reviewed operator classes | 03, 09–10, 12–15, 21, 24–28, 33 | Approved SQL and business-result goldens |
| Early Oracle dialect and preflight gates | 05, 12, 14–15, 22, 24–26, 33 | Approved Oracle test instance |
| Professional coding and Codex engineering standards | 01, 17, 25–28, 30 | CI pipeline results once code exists |
| Versioned source provenance, cache and session safety | 05, 08, 18–20, 23, 27 | End-to-end trace and authorization replay tests |
All measurements and company approvals remain pending until performed by named owners. Source original retained unchanged in its previous folder.

## V4.2 change — existing UI only (2026-10-16)
- User supplied actual HTML/CSS/JS browser assets and instructed no new UI development.
- Updated scope/product/API/UX/deployment/roadmap/ADRs/Codex/test documentation to backend-first and mandatory EWS API compatibility at later integration.
- Added [35 Existing EWS UI Contract](./35_EXISTING_UI_INTEGRATION_CONTRACT.md), frozen copies of the three supplied assets, and `CODEX_BACKEND_ONLY_HANDOFF.md`.
- Removed current React/TypeScript/Vite/new-screen deliverables and development-time frontend toolchain gates; retained all backend semantic, graph, SLM, SQL, Oracle, authorization, data evaluation and ops plans.
- Recorded production blockers in supplied UI: local-demo bearer token placeholders, client-selected `user_id`, optional STT settings and external CDN dependencies. No modification to the three supplied asset contents.
