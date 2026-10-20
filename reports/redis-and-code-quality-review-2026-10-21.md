# Redis and application quality follow-up — 2026-10-21

What this change does: The backend now uses real standalone Redis for shared
request-rate quotas and active-chat admission across API workers. Durable
conversation/metadata storage remains separate. The review also closes concrete
session authorization, retention, byte-budget and deadline gaps without editing
the supplied UI.

Assumed deployment: one VM, multiple API processes, standalone private Redis.
Actual VM OS, hardware, model capacity and peak workload are unknown. Eight active
chats globally, one per tenant/subject and two API workers are provisional budgets,
not a certified simultaneous-user capacity. This supersedes the old single-process
Redis recommendation in the historical 2026-10-20 audit.

## Implemented and checked

| Area | Result |
|---|---|
| Rate admission | Atomic rolling-minute Lua quota; stable tenant/subject hash; shared across workers; 60-second expiry |
| Active chat admission | Atomic global/per-principal leases around both chat routes; unique tokens; exceptional cleanup; expired leases cannot release newer work |
| Redis failure | Bounded pool/timeouts; no mutation retries or memory fallback; safe 503; liveness remains available |
| Readiness | Authentication and actual Lua/sorted-set capability probe; no company database or model connection in check-redis |
| TLS | Explicit certificate/hostname checks, optional approved CA file; trusted/untrusted/hostname-negative local TLS probes |
| Local setup | Loopback Docker Compose service; random separate application/test credentials; restricted ACL/key scopes; no source-control secrets |
| Environment | Actual local .env created only when absent; explicit selection; office template keeps real Redis URL out of source |
| Worker startup | Actual two-worker CLI exercised over HTTP; both worker PIDs observed; spawned workers initialize structured logging |
| Durable sessions | Redis restart leaves saved conversations intact; SQLite remains the synthetic durable store |
| Session authorization | Application SessionService rechecks current identity before/after reads; governed publication during history read is rejected |
| Sidebar privacy | Generic public titles prevent old question text appearing after access changes; message scope redaction remains |
| Retention | Expired records remain owner-deletable; bounded explicit purge-sessions maintenance with cascaded message deletion |
| Session resource budgets | 200-message ceiling and four-million-byte UTF-8 history budget; reject oversized legacy reads before materializing bodies |
| Session query/index behavior | Session/message index supports ordered history reads, byte-budget queries and cascading retention deletes without scanning unrelated conversations |
| Session deadlines | Reject expired requests before writes; bound cross-process SQLite writer waits to remaining request budget |
| Structure | Domain/application/infrastructure/API/bootstrap ownership retained; infrastructure boundary added to existing AST enforcement |
| UI | No browser work or asset changes; original SHA256 preservation remains mandatory |

The existing compiler, independent SQL validator, capability gate, exact Decimal
output, server-derived identity, governed metadata publication and raw-SQL denial
remain in place. Redis contains no business results, grants or approval authority.
No Redis history cache, speech provider, vector server or new model runtime was added.

## Folder structure verdict

The current modular package is appropriate. Another wholesale move would not
improve the dependency direction. Keep:

```text
backend/nl2sql/
  domain/          # Immutable contracts
  application/     # Reporting/session/metadata use cases and typed ports
  infrastructure/  # Redis, identity, persistence, retrieval and inference adapters
  api/             # HTTP contracts and transport
  bootstrap/       # Composition and resource lifecycle
  cli/             # Explicit operator commands
  evaluation/      # Fictional fixtures and evaluation
tests/             # Unit, contracts, integration, security, evaluation and tooling
config/            # Sanitized configuration and optional local Redis Compose
scripts/           # Quality/evaluation/local-setup entry points
docs/              # Current architecture/configuration/operations and original design
UI/                # Canonical frozen reference
```

Generated databases, credentials, logs, build outputs and local verification scripts
are ignored runtime artifacts. Their presence does not make them source modules.
See [Structure](../docs/STRUCTURE.md) for the full ownership rules.

## Must complete before restricted office release

1. **Corporate identity remains unqualified.** The supplied adapter supports local
   opaque tokens and verified HS256 JWTs, not a demonstrated corporate SSO/key
   lifecycle. Integrate the approved identity provider and test offboarding,
   rotation and revocation. Otherwise local synthetic authentication would be
   mistaken for enterprise identity assurance.

2. **Office Redis, Oracle and inference need actual environment qualification.**
   Local Redis probes do not prove VM credentials, corporate CA trust, DBA grants,
   Oracle context reset/cancellation, certified business meanings or real model
   behavior. Run the prepared checks with approved identities and synthetic office
   fixtures, then measure sustained HTTP/model/database capacity. Otherwise the
   provisional worker/pool/admission settings can overload the target resources.

3. **Restricted storage and operational ownership need approval.** The development
   checkout is under OneDrive; ignored paths do not disable sync or enforce ACLs.
   Select approved non-synchronized runtime paths, the durable production session
   store, backup/restore and retention policies, protected audit/monitoring sinks,
   ingress/TLS and process supervision. Otherwise files, recovery or audit evidence
   could fail office requirements despite passing source tests.

## Should complete as workload requirements are established

4. **Retries can repeat read-only work.** Active admission prevents simultaneous
   work by a user at the configured limit, but a sequential duplicate request can
   still repeat inference and SQL after the first finishes. Add authenticated
   request-id deduplication if client retries/repeated costs require it. It is not
   represented as implemented here.

5. **One VM/one Redis is not high availability.** Lease expiry recovers crashed
   admission state; it cannot forcibly cancel a hung native call. Redis restart or
   eviction can reset quota/lease state. Drain work for planned Redis maintenance,
   retain provider-side timeouts/pools and noeviction, and qualify any HA/Cluster/
   Sentinel design separately. Otherwise temporary state loss can admit overlapping
   work even though old requests cannot return a successful admitted response.

6. **Result/history caching needs evidence.** Direct durable reads are correct for
   the current implementation. Add a history cache only after measuring a useful
   benefit and defining permission/version invalidation and delete propagation.
   Business-result caching remains disabled pending explicit freshness/access policy.

## Reproducible checks and evidence

Use [Operations](../docs/OPERATIONS.md#redis-verification) for setup and exact commands.
The complete gate is `python scripts/check.py --redis-env .local/redis/test.env`.
The default gate does not silently connect to a Redis service.

Additional actual local evidence:

- [Outage/recovery](redis-outage-verification-2026-10-21.json): readiness/chat 503
  during a real Redis stop, liveness 200, recovery to 200 and saved history preserved.
- [TLS](redis-tls-verification-2026-10-21.json): trusted test certificate accepted,
  untrusted certificate and wrong hostname rejected. This is not corporate PKI qualification.
- [ACLs](redis-acl-verification-2026-10-21.json): anonymous, other-namespace and
  configuration access denied; missing expiry permission rejects readiness without
  leaking probe keys; generated application password absent from source files.
- [Package](redis-package-verification-2026-10-21.json): all 78 package source/marker
  files match the final wheel byte-for-byte; isolated wheel readiness reaches real
  Redis and unauthenticated chat is rejected.

Final verification completed:

- Pre-publication dependency audit identified the certifi CA-bundle advisory
  [GHSA-6q48-6c7w-9gw2](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2).
  Core and development lockfiles now pin certifi 2026.10.19. Re-auditing all 55
  pinned development/optional dependency entries reported no known vulnerabilities;
  [the refreshed audit](dependency-audit-v43.json) records the result. This is a
  dependency advisory check, not a live application penetration test.
- Duplicate frontend files and three obsolete raw quality-console logs are removed
  from the published tree. The byte-identical duplicate dependency audit is also
  untracked; ignored local copies remain available. Canonical UI assets and the
  retained JavaScript contract test have Git byte-preservation attributes.
- Mandatory gate: **401 passed, no skipped tests, 89% combined statement/branch coverage**.
- Ruff correctness/import and format checks passed; Pylint **10.00/10**;
  strict Pyright **zero errors/warnings**; pre-commit passed.
- Fresh final Redis/API/worker/adapter regression run: **31 passed**.
- Real Redis connection-pool exhaustion returned safe 503 and recovered after the
  held connection was released. Quota correctness tests use an explicitly larger
  test pool/time budget so client-pressure behavior does not confound Lua assertions;
  production defaults remain 16 Redis connections per worker and 0.5-second I/O budgets.
- Dependency consistency (`pip check`), source whitespace checks and unchanged UI
  SHA256 preservation passed. The suite reports one existing Starlette TestClient
  dependency deprecation warning; no unapproved dependency was added to hide it.

Verdict: The modular structure and Redis integration are a tested local foundation.
Complete office qualification items 1–3 before restricted deployment.

Not checked: corporate endpoints, actual VM capacity/ACLs/backups, enterprise SSO,
real Oracle/model/native-vector behavior, browser integration or a live penetration
test. No production deployment, company metadata publication or model-weight download was performed.
