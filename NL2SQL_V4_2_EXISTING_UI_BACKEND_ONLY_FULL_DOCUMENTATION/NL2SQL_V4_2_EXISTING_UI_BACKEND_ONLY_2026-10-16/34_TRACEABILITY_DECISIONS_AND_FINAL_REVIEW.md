# 34 — Cross-Document Traceability, Open Decisions, Final Review and No-Code-Until-Gate Checklist

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Pre-development design review. **Owner:** Technical architect. This is a *traceability plan*; it cannot itself approve company permissions or satisfy test requirements that need running code.

## Single authoritative design
**V4.1 Refined** = V4 Hardened governance + *certified semantic views as a catalog abstraction* + deterministic lexical baseline + optional locally benchmarked embeddings + verified in-memory join graph + typed Gemma plan + compiler-first SQL + strictly gated fallback + independent SQL/business/authz checks + early Oracle dialect qualification + provenance and measured coverage/performance.

## Canonical technology/approval register
| ID | Technology or policy | Default | Decision status |
|---|---|---|---|
| ADR-001 | Query plan and compiler | Typed Pydantic DSL, deterministic SQL first | Proposed architecture |
| ADR-011 | Semantic views | Logical catalog view first; approved Oracle views optional | Proposed, business/DBA/security review |
| ADR-012 | Keyword search | SQLite FTS5/BM25 + exact aliases over metadata | Proposed, platform review |
| ADR-013 | Embedding/vector | Local approved encoder + FAISS, **disabled by default** | Benchmark/policy gate |
| ADR-014 | Relationship graph | NetworkX in-process from certified physical edges | Proposed, DBA/data review |
| ADR-015 | SQL fallback | Disabled by default, per-domain reviewed operation classes | Security + DBA signoff |
| ADR-016 | Early Oracle tests | In parallel with compiler when approved test DB exists | DBA approval and access gate |
| ADR-017 | Code quality | Ruff, Pylint complementary, strict Pyright, pytest, backend CI, AGENTS.md; later JS/browser checks | Team/company standard approval |
| ADR-018 | Promotion metrics | Paired A–G ablation and coverage+answer accuracy | Benchmark first, thresholds owner-approved |
| ADR-019 | UI fixed by user | Sole uploaded EWS HTML/CSS/JS UI; build backend only; legacy adapter mandatory, integrated later | User-selected; auth/browser production security still pending approval |
| ADR-020 | Business database | Oracle read-only identity + separate session write store | Security/DBA approval |

## Requirement-to-design-to-test matrix
| Requirement | Owner document | Companion | Proof before release |
|---|---|---|---|
| Metric meaning, data grain, historical definitions | 04 | 31, 07 | Approved domain goldens, lineage/grain fixtures |
| Physical catalog and source reconciliation | 05 | 33 | Approved dictionary mapping, drift and rollback |
| Authz-filtered search, exact/BM25/vector | 06 | 32 | Allowed-scope retrieval ablations, leakage tests |
| Physical join/path correctness | 07 | 31 | Composite/fan-out/as-of golden results |
| Secure entity resolution | 08 | 21 | Permission/alias collision tests |
| Confidence routing and clarification | 09 | 02 | Held-out disambiguation suite |
| Typed QueryPlan and model output | 10, 11 | 27 | JSON/schema/generation tests |
| Compiler-first Oracle SQL | 12 | 31, 33 | Query/result equivalence, Oracle dialect cases |
| Restricted fallback | 13 | 14, 33 | Operation-class authorizations, security and golden outcomes |
| Independent validation | 14, 15 | 21 | Deny suite, DB-grant proof and cost limits |
| EWS contract and sessions (UI later) | 16, 17, 18 | 19, 35 | Backend legacy DTO/API E2E now; browser accessibility later |
| Cache, telemetry and deployment | 20, 22, 23 | 30 | Load/timeout/drift and privacy runbooks |
| Accuracy vs coverage | 24 | 32 | Reproducible paired A–G benchmarks |
| Code standard and repository rules | 28 | 30 | Real CI output once source exists |
| Enterprise rollout | 25, 26 | 33 | Company signoffs and go/no-go |

## Open decisions — do not silently close
1. Exact business definitions, selected initial domain, grain/date/fiscal rules, authorized physical schema and VPD controls.
2. Whether corporate approved environment allows SQLite metadata indexes, NetworkX/FAISS licenses, local embeddings, specific Gemma checkpoint and runtime.
3. **Resolved by user:** use supplied existing EWS UI exclusively. Still open: approval for secure auth migration, hosting/CSP, speech and any later minimal UI patch.
4. DBA approved Oracle test environment, DB version and view creation policy.
5. Query grammar coverage, fallback operation allowlist, exact resource/time/row budgets, authorized data/result caching.
6. Required business accuracy and coverage threshold, false automatic-routing tolerance, p95 and concurrency targets—set *before* evaluating architecture variants.
7. Enterprise application and inference hosting rights, service secrets, private networking and approved session store.

## Approval stages
**Architecture review:** P0 docs and ADR defaults accepted by named reviewers, unresolved company-specific items documented as gates. **Synthetic coding gate:** `AGENTS.md`, typed ports, test fixtures, CI policy established; code may proceed using synthetic data only, without Oracle/production approval. **Office integration gate:** sanctioned source catalog, approved data definitions and Oracle test access. **Production gate:** security, DBA, operations, domain metric steward, reproducible golden results, privacy and rollback validation.

## Doc maintenance rules
All changes to typed models, view definitions, embedding mode, graph proof, fallback grammar or Oracle privileges require updating owning document, dependent contracts, ADRs, benchmark fixtures and release checklist. A new technology choice is not automatically 'selected in production' because it appears in a planning document.

## Reviewer signoff record (blank until authorized)
| Area | Responsible reviewer | Decision/status | Date/evidence |
|---|---|---|---|
| Product scope/existing UI | User selected supplied UI; product/security production approval | UI choice fixed, integration signoff pending | User request 2026-10-16 |
| Metric and semantic views | Domain owner | Pending | — |
| Physical schema/join proof | DBA | Pending | — |
| Auth and SQL safety | Security owner | Pending | — |
| SLM and local embedding/runtime | ML/platform | Pending | — |
| Benchmark/quality bar | QA lead | Pending | — |
| App/model/database deployment | Ops/platform | Pending | — |

**No claim of completed code/tests/enterprise approval is made in this file.**
