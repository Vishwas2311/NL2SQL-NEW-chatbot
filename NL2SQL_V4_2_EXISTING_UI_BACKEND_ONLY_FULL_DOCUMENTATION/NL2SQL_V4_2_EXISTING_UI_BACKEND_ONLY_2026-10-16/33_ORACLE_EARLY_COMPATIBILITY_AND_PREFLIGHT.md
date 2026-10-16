# 33 — Early Oracle Compatibility Qualification, Query Preflight and Data-Scope Gate

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Proposed engineering and release gates. **Owners:** DBA, backend compiler lead, security, platform. **No office Oracle access, grants or tests are asserted.**

## Problem being solved
SQLite is valuable for synthetic semantics and orchestration but cannot establish that compiler SQL is valid, accurate or safe in the target Oracle release. Delaying Oracle validation to the end risks expensive late compiler redesign. Conversely, external or unauthorized Oracle connections are prohibited. Therefore dialect compatibility testing starts **as soon as an approved Oracle test environment and sanitized fixtures are available**, in parallel with implementation milestones—not by bypassing approval.

## Two-tier compatibility strategy
**Tier 1 — Safe local:** Parser/rendering unit tests, typed bind contract tests, SQL AST/deny fixtures, synthetic SQLite *logical* business-result tests; no claims that SQLite executes Oracle dialect equivalently.

**Tier 2 — Office-only authorized:** Oracle release/driver qualification against synthetic approved Oracle test schema, DBA-owned grants, VPD/policy rules, actual Oracle query optimizer controls, independently checked expected results and security. Never use production customer rows for development fixtures.

## Oracle compatibility matrix
| Behavior | Test fixture | Required evidence |
|---|---|---|
| Driver mode/version | Thin/Thick and supported DB version | Connection/driver report, auth scheme approval |
| Bind parameters | Strings, numbers, dates, arrays as allowed | Correct types, injection rejection |
| Identifier names | Quoted/unquoted schema/view and synonyms | Exact allowlist behavior |
| Dates & as-of | TZ, fiscal boundary, snapshots | Independently checked historical results |
| NULL / numeric | Precise decimal, divide by zero, null aggregates | Typed expected result |
| Pagination | `FETCH FIRST`, stable ORDER BY | Deterministic top-N results |
| Analytic windows | Approved window class | Query equivalence golden |
| CTE and pre-aggregation | Multiple many-side sources | No fan-out numerical inflation |
| Views and DB policies | DBA-approved views, row/column scope | Cross-user denial and permitted results |
| Time/resource | Timeout, cancellation, limited execution | Bounded resource use and cleanup |

## Execution security protocol
`ValidatedQuery` with principal, catalog/view/policy digests and typed bind definitions → verify expiry and authorizations → optional approved cost/plan estimation → check hard configured limits and operation allowlist → acquire read-only connection with DB-enforced access policy → bind parameters → execute under statement/resource limits → cap/paginate returned rows → safe error and audit reference. Explain-plan/cost estimates are **advisory**, not security proofs and not hard runtime guarantees. DB controls must enforce denied access even if Python policy fails.

## Safety and fallback
Only SELECT-compatible approved statements; reject DDL/DML/PLSQL, DB links, dangerous functions, multiple statements and any operation missing physical or metric proof. A parse-valid statement can still be wrong; complex fallback requires independently verified results per promoted operation class. A DBA must explicitly approve physical semantic view creation and dependent grants.

## When enterprise test access isn't available
Record `ORACLE_VERIFICATION_BLOCKED` and continue synthetic local development. Do not claim Oracle feature compliance or permit deployment until tier-2 tests pass. Keep direct customer/business source schemas inside the approved environment. Generic code and fictional fixtures can be developed externally if company policy permits.

## Deliverables and release gates
Oracle-version-qualified dialect matrix, sanitized integration fixtures, run commands/evidence, DBA grants and row-policy proof, cost/timeout/cancellation result log, feature-specific rollout decisions. DBA/security signs off tier 2 before enterprise rollout. Cross-reference 12/14/15/21/22/24/25.
