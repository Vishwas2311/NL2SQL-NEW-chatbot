# V4.2 Existing-UI Backend-Only — Complete NL-to-SQL Design Package

**Date:** 2026-10-16  
**State:** DRAFT FOR REVIEW. No application code, Oracle connection, benchmark, or enterprise approval is claimed.  
**Supersedes for UI scope:** V4.1 Refined documentation. The uploaded EWS vanilla HTML/CSS/JS is the only UI and will be integrated later; the V4.1 backend architecture is retained.

## Start here
1. [00 Master Register](./00_MASTER_DOCUMENT_REGISTER_AND_PRECODING_CHECKLIST.md) — complete numbered document register and signoff procedure.
2. [34 Traceability and Decisions](./34_TRACEABILITY_DECISIONS_AND_FINAL_REVIEW.md) — proposed technology choices, owners, unresolved gates and proof obligations.
3. [03 Canonical Architecture](./03_SYSTEM_ARCHITECTURE_AND_RUNTIME.md) — request paths and trust boundaries.
4. [31 Governed Semantic Views](./31_GOVERNED_SEMANTIC_VIEWS_AND_COVERAGE.md) — what changed most in business query design.
5. [32 Retrieval Experiments](./32_RETRIEVAL_TECH_CHOICES_AND_EXPERIMENTS.md) — exact + FTS5 baseline, optional encoder/FAISS, NetworkX.
6. [33 Oracle Compatibility](./33_ORACLE_EARLY_COMPATIBILITY_AND_PREFLIGHT.md) — authorized early DB test plan.
7. [30 Professional Coding Standards](./30_CODING_STANDARDS_CODEX_AND_CI.md) — initial Codex task and CI gates.
8. [35 Existing EWS UI Integration Contract](./35_EXISTING_UI_INTEGRATION_CONTRACT.md) — read this before any backend API work; **do not build a UI**.
9. [25 Implementation Roadmap](./25_IMPLEMENTATION_ROADMAP_DEPENDENCIES_AND_GATES.md) and [24 Evaluation](./24_TEST_DATA_EVALUATION_AND_BENCHMARKS.md).

## Fixed product UI
**Only the uploaded EWS HTML/CSS/JavaScript UI is to be used**, and integration is deferred. Reference snapshots are included in `existing_ui_reference/` for contract verification, **not as a frontend to build or deploy now**. `/ews-chatbot/*` compatibility is mandatory at the later integration gate; no new React/TypeScript/Vite app is required.

## Technology decision in plain language
- **Default search:** Exact aliases + embedded SQLite FTS5/BM25 over *approved metadata*.
- **Optional semantic search:** Local embedding encoder + FAISS; feature flag off until validated in the A–G benchmark. FAISS is not a vector DB server.
- **Join graph:** NetworkX *in-memory* from certified physical join edges. No mandatory Neo4j.
- **Business graph / Graphify:** Not required; candidate inputs only if independently reconciled and approved.
- **SLM:** Gemma 4 12B as a replaceable local baseline, not a proven best checkpoint.
- **SQL:** Certified logical views + typed plan DSL + compiler; broad SQL fallback disabled by default, reviewed narrow operator classes only.
- **Business database:** Oracle, with approved test/production access and DB-enforced permissions.
- **Quality:** Ruff + complementary Pylint + strict Pyright + pytest + backend API compatibility tests, CI, Codex AGENTS instructions. No new frontend toolchain.

## Not yet decided or proven
Exact business metric definitions, office physical schema and VPD grants, chosen initial domain, corporate dependency/licenses, Oracle DB release/infrastructure, embedding checkpoint, model runtime, p95/accuracy/coverage thresholds, DBA approval for Oracle views and fallback allowlist. Use synthetic fixtures only until authorized integration. Never export original banking schemas or customer records outside approved enterprise systems.

## Codex instructions for this change
[Backend-only Codex handoff](./CODEX_BACKEND_ONLY_HANDOFF.md). This replaces the previous prompt's request to scaffold React/TypeScript and visual screens.

## Contents and verification
35 retained and UI-scoped numbered design files plus new document 35, consolidated architecture regenerated from those files, original change log updated, and automated report of file/reference consistency. [Revision/validation report](./RELEASE_VALIDATION_REPORT.md). All editable source files are Markdown.
