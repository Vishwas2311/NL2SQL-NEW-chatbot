# Development hardening — external release gates remain open

Local quality verification is complete: 323 passed, 89% coverage and all six quality gates.
See reports/DEVELOPMENT_HARDENING_REPORT.md for the full implementation and evidence.

Still requires approved qualification: company Oracle/DBA controls, actual embedding runtime,
real private/hosted inference, native FAISS, corporate identity, HTTP capacity, interruption of
unspecified native model work, company freshness/startup/scheduler/retention/monitoring policies.
No production readiness, external publication or deployment is claimed. Existing unsupported
advanced SQL semantics remain explicit; raw SQL fallback stays disabled.

UI bytes match all six original hashes. Numbered documents were untouched; their pre-existing
CRLF/LF manifest differences are documented in reports/preservation-hardening.json.

# Historical V4.3 status

The V4.3 lifecycle is implemented. See SCHEMA_IMPLEMENTATION_REPORT.md, SCHEMA_EVOLUTION_TEST_RESULTS.md and ORACLE_BOOTSTRAP_RUNBOOK.md. The V4.2 record below is historical; its former missing metadata workflow has been added.

# Open blockers and explicit limits

The missing-documentation/UI-manifest blocker is resolved. Original expected hashes were retained.
The synthetic backend is usable; enterprise release is blocked by the items below.

| Item | Local evidence | Required next evidence / authorization |
|---|---|---|
| Real Gemma | Strict private adapter and scripted/HTTP transport tests | Approved exact checkpoint/runtime/host, structured-output compatibility, representative real inference, token/accuracy/load evidence; no download without approval |
| Oracle deployment | Driver pool contract, both SQL dialects, native DATE/NUMBER/limits/cancel/cleanup tests | Approved synthetic Oracle schema and credentials, release/version mapping, DBA VPD/context reset, least-privilege grants, resource manager, cost/preflight and real precision/time/cancellation tests |
| Enterprise identity | Random local tokens and validated HS256 JWT/current server grants | SSO/JWKS/rotation, live entitlement revocation and distributed quota adapters |
| Business certification | Four fictional views with explicit time/unit/grain contracts | Steward-owned production definitions, calendars, masks, certified keys and source freshness |
| Advanced operators | Certified ranges/fiscal/net/ratio/CTEs/multi-fact/ranking supported | Arbitrary formulas/CTEs/windows/joins, average/ratio sorting/HAVING, period-over-period/timezone timestamp business semantics remain unsupported; fallback stays disabled |
| Retrieval promotion | Exact/BM25 and optional scope-safe hybrid harness | Approved encoder and domain-held-out paired business-result benchmark; no FAISS/server installed |
| Release evaluation | 46 distinct scripted-plan local workflow cases plus adversarial tests | Domain-owned 150+ held-out launch corpus, real Gemma/second-model and A-G comparisons, signed accuracy/coverage/SLO thresholds |
| Semantic administration | Pinned JSON validation and atomic snapshot pointer | Named signatures/approvals, enterprise reconciliation and administrative bundle publication/rollback; local updates require restart |
| Shared operations | Bounded sessions, local quotas, read pools, safe logs | Distributed idempotency/cancellation, shared limits, purge/encryption/backups, production monitoring and crash/load qualification |
| Speech | Authenticated explicit 501 | Approved provider and MIME/size/duration/locale/retention rules |
| Ponytail lifecycle | Official 5.2.0 installed/enabled; configuration has trust hashes | /hooks runtime confirmation and fresh-thread execution evidence. Trust records were not edited by this agent |
| UI integration | Original assets and backend compatibility verified | Separate integration/browser authorization; existing hardcoded UI placeholders are not authentication |
| Deployment / release | Local gates and dependency advisory scan | Approved source hosting/CI, infrastructure/residency, license/SBOM, penetration/egress review and release signoffs |

No model weights, real Oracle/company data, third-party model/vector server, source publication or
production deployment was used. SQLite and fake-driver tests cannot certify real Oracle or Gemma.

## V4.3 release blockers

No authorized corporate Oracle endpoint, dictionary grants, read-only query identity, DBA context routines or business/security-certified catalog. No approved real Gemma checkpoint/endpoint or embedding model; native FAISS not installed/qualified. General SCD2/MoM/YoY/LAG/LEAD/running-total extensions remain unsupported. Corporate identity/trust distribution, restricted-storage ACLs, backups, multi-node HA/load, security/privacy/license review and deployment approval are external gates. Ponytail hook execution remains unverified. Local synthetic lifecycle is usable; production readiness is not claimed.
