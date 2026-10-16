# 26 — Architecture Review, RACI, Decision Log and Signoff

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Draft for review; no implementation or company production validation performed.  
**Document owner:** Architect + product + DBA + security  
**Gate:** P0  
**Baseline reference:** V4 research/blueprint supplied on 2026-10-15.  
**Data policy:** Fictional examples only; actual company schema and customer data stay in approved office systems.

> **Core distinction:** this document specifies future behavior. It does not claim that these modules, controls, model benchmarks, or Oracle permissions are already deployed.

## Design specification

## Approval responsibilities
| Deliverable | Responsible | Accountable/approver | Consulted |
|---|---|---|---|
| PRD, personas, answer UX | Product/UX | Product owner | Compliance, users |
| Catalog, metric definitions | Data engineers/stewards | Business metric owner | DBA, security |
| Oracle joins and physical schema | Backend + DBA | DBA/data owner | Domain steward |
| Auth and query policy | Security/backend | Security owner | DBA |
| Gemma model/runtime | ML/platform | AI platform owner | Security/ops |
| SQL compiler and fallback | Backend/ML | Technical architect | DBA, security |
| Quality benchmarks | QA/ML | QA lead + business owner | DBA |
| Production deployment | Platform/SRE | Operations owner | Security, DBA, product |

## Decisions to explicitly lock before implementation
- **D-01 UI resolved by user:** use uploaded EWS HTML/CSS/JS exclusively. Backend compatibility is mandatory; integrating assets and security hardening are later, separate gates. No React implementation.
- **D-02 SQL scope:** broad ad-hoc business queries vs certified reporting only; this affects compiler/fallback coverage.
- **D-03 SLM:** exact Gemma checkpoint, local/runtime capability and external egress policy.
- **D-04 Catalog authority:** metric steward, physical schema owner, effective-date/fiscal rule owner.
- **D-05 Vector:** baseline benchmark before enabling production vector dependency.
- **D-06 Value lookup:** allowed identity fields, fuzzy matching and data classification.
- **D-07 Oracle:** test DB version, grants, supported functions and resource limits.
- **D-08 Deployment:** app placement, internal model GPU endpoint, session store, backup/persistence.
- **D-09 Service levels:** concurrency, max query time, p95 and availability targets.
- **D-10 Governance:** audit retention, CSV, chart and speech feature flags.

## Signoff rule
A document can be `DRAFT`, `IN_REVIEW`, `APPROVED`, or `BLOCKED`. Approval requires named owner, date, accepted ADRs and closed critical questions. No model claims, screenshot-derived office details or suggested thresholds are considered verified production facts until reviewed by the appropriate owner.

## Change control
If a decision changes, update the relevant doc, its dependencies, impacted contracts and golden tests. Signoffs are invalidated when modifications affect permissions, metric calculations, Oracle SQL safety or deployment/network boundaries.



## V4.1 decisions requiring explicit approval
| ID | Decision | Proposed baseline | Responsible approval |
|---|---|---|---|
| ADR-011 | Governed semantic view abstraction | Catalog-side logical views first; physical Oracle views only when DBA-approved | Domain owner + DBA + security |
| ADR-012 | Lexical provider | SQLite FTS5/BM25 as embedded default if permitted | Platform + security |
| ADR-013 | Optional vector implementation | Local approved encoder + FAISS, disabled until benchmark gate | ML + security + platform |
| ADR-014 | Graph implementation | NetworkX approved in-memory graph; no Neo4j initially | Data architect + DBA |
| ADR-015 | Restricted SQL fallback | Disable pending per-domain operator allowlist and goldens | Security + DBA + domain owner |
| ADR-016 | Oracle compatibility timing | Tests parallel to compiler if approved test DB available | DBA + platform |
| ADR-017 | Coding standards | Ruff/Pylint, strict Pyright, pytest, CI, AGENTS.md; optional later JS integration checks | Tech lead + security |
| ADR-018 | Benchmark promotion | Evaluate paired A–G configurations, thresholds TBD by owner | QA + product + ML |
No table here falsely records an *approved* enterprise action. Open decisions: physical view creation rights, company coding stack restrictions, exact SLM weights and local embedding license, SQL operator coverage, production DB resource grants, p95/coverage thresholds, authorized source metadata. See [34](./34_TRACEABILITY_DECISIONS_AND_FINAL_REVIEW.md).

---

## Deliverables / artifacts to review

RACI, ADR decision checklist, reviewer register, signoff form and issue log

## Acceptance tests and exit criteria

Every P0 decision has approver; production releases blocked by open security or data-definition issues

## Open decisions and evidence required

Who owns each approval? Which documented decisions can be considered already authorized?

## Related documents

[01](./01_SCOPE_PRD_AND_NFR.md), [03](./03_SYSTEM_ARCHITECTURE_AND_RUNTIME.md), [04](./04_SEMANTIC_CATALOG_AND_GOVERNANCE.md), [21](./21_SECURITY_PRIVACY_THREAT_MODEL.md), [22](./22_PRIVATE_DEPLOYMENT_INFRA_AND_FULCRUM.md), [24](./24_TEST_DATA_EVALUATION_AND_BENCHMARKS.md), [25](./25_IMPLEMENTATION_ROADMAP_DEPENDENCIES_AND_GATES.md)


---

## Document approval worksheet
| Field | Example placeholder |
|---|---|
| Document ID | 08 — Entity and Value Resolution |
| Revision | r1 |
| Reviewer | Named business/security reviewer |
| Decision | Approved / Changes needed / Blocked |
| Conditions | Approved searchable identity fields, rate limits |
| Evidence | Synthetic ambiguous lookup tests, privacy review |
| Date | YYYY-MM-DD |

### Open issue register template
`ISSUE-ID, severity, doc refs, decision required, candidate options, responsible owner, requested_by, due date, evidence link, final disposition, ADR ID`. No issue with `critical` or `policy-blocking` status may be silently closed by choosing a model-generated assumption. The owner must explicitly resolve it.

---

## Historical V4 Baseline Requirements (reference only; superseded where V4.1 refines them)

> **Historical UI exclusion:** Any older requirement below to create a React/TypeScript/Vite frontend, new browser pages, screens, or UI build/test pipeline is superseded by the user decision. These are historical notes, **not implementation tasks**. Preserve existing capabilities for later integration via document 35.

> This is preserved from the earlier planning draft for comparison. The current V4.1 design section, companion docs 30–34, the approved ADR register, and subsequent validated contracts take precedence on changes explicitly addressed in the V4.1 refinement. Historical descriptions of optional vector providers, open SQL fallback, and late Oracle tests are **not** new mandatory decisions.


The following material records relevant requirements from the previously agreed V4 blueprint. The sections above are the detailed module design and take precedence where they add stricter controls. Original V4 is a **proposed architecture**, not independently verified production source.

# 26. Module Ownership and Dependencies

| Component | Primary implementation responsibility | Depends on |
|---|---|---|
| Existing UI owner (later integration) | Backend API team + product | EWS compatibility and security review |
| FastAPI | Backend engineering | Identity and request models |
| Semantic catalog | Data/AI engineering | Approved business definitions |
| Retrieval | AI/search engineering | Catalog and access policy |
| Join graph | Data/backend engineering | Verified physical relationships |
| SLM service | ML engineering | Approved model runtime |
| Query planning | AI/backend engineering | Catalog and SLM adapter |
| SQL compiler | Backend/data engineering | Query DSL and semantic rules |
| Validator | Backend/security engineering | SQL policy and metadata |
| Oracle adapter | Backend/DBA | Approved DB access |
| Session manager | Backend engineering | Identity and persistence |
| Evaluation | QA/AI engineering | Golden datasets and baselines |
| Production | Platform/operations | All release gates |

Several roles may be performed by the same engineer on a small team, but approval responsibilities should remain appropriately separated.

---

---

# 28. Decisions We Are Locking

| Architecture question | Final decision |
|---|---|
| Build full chatbot from scratch? | Yes |
| Backend framework | FastAPI |
| Frontend | Existing user-supplied HTML/CSS/JavaScript; later integration only |
| Primary database | Oracle |
| Development database | Synthetic SQLite |
| Primary model | Gemma 4 12B baseline |
| Model tightly coupled to backend? | No |
| Semantic catalog required? | Yes |
| Business metric governance? | Yes |
| Verified SQL relationships? | Yes |
| Graphify required? | No |
| Neo4j required? | No |
| Dedicated vector DB required? | No |
| Exact/keyword retrieval? | Yes |
| Embeddings? | Optional, benchmark-driven |
| Structured query plans? | Yes |
| Deterministic SQL compiler? | Yes |
| Complex-query SLM fallback? | Yes, restricted |
| Independent SQL validation? | Mandatory |
| Read-only business query identity? | Mandatory |
| Multiple AI agents? | Not initially |
| Fine-tuning? | Only after baseline evaluation |
| Private inference? | Required |
| Full observability? | Required |
| Business-result evaluation? | Required |

---
