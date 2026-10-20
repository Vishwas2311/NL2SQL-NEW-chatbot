# Application architecture and IAM review — 2026-10-20

Follow-up implementation: the user subsequently confirmed concurrent VM users and
an existing Redis service. Shared Redis admission and the layered source structure
have now been implemented; see [current architecture](../docs/ARCHITECTURE.md) and
[code structure](../docs/STRUCTURE.md). This document records the earlier baseline.
Its other IAM, retention and office-qualification findings are not marked resolved
by the folder move or Redis addition.

2026-10-21 follow-up: real Redis connectivity/active-chat admission and the session
authorization, title, retention, byte-budget, deadline and indexing fixes are now
implemented. See the [latest review](redis-and-code-quality-review-2026-10-21.md)
for current status and remaining office qualification. The findings below retain
the original audit evidence and are not a claim that those fixes are still absent.

What this repo does: This is a governed natural-language reporting backend. It turns approved questions into typed plans, compiles SQL, independently checks it, and executes read-only queries within the authenticated user's grants. Its current working environment is synthetic SQLite; office Oracle, corporate identity and real model inference remain qualification work.

Assumed load: one approved Windows machine, one API process, normally one to ten simultaneous office users. Higher concurrency is a qualification target, not an established capacity. The office UI remains unchanged and was not opened or integrated.

**Architecture decision**

Keep the modular FastAPI application and the current local SQLite stores. Do not add Redis yet. Redis is absent from the runtime dependencies, configuration and adapters. The user delegated the Redis choice during this review; no Redis installation or migration was performed.

| Responsibility | Current implementation | Recommended initial choice |
|---|---|---|
| HTTP/API | FastAPI, bound to 127.0.0.1 by the CLI | One local process |
| Identity | Opaque local tokens or HS256 JWT, resolved to server-owned principals | Keep for synthetic use; qualify corporate sign-in before restricted use |
| Session history | Separate writable SQLite database with ownership and compare-and-swap updates | Keep durable local storage; fix retention and authorization gaps below |
| Metadata approvals/publication | Private SQLite WAL repository, signed evidence, atomic active pointer | Keep durable authority separate from temporary caches |
| Metadata search | Exact aliases and permission-partitioned in-memory SQLite FTS5/BM25 | Keep |
| Join relationships | In-process NetworkX graph from certified relationships | Keep |
| Query planning | Exact certified templates; optional typed model provider | Templates work locally; actual model needs separate qualification |
| SQL | SQLGlot compiler, independent AST/policy checks, signed short-lived capability | Keep all three gates |
| Query execution | Read-only synthetic SQLite; gated Oracle adapter | Synthetic locally; approved Oracle inside the office environment later |
| Vectors/embeddings | Disabled by default; optional adapters and contract tests | Leave disabled until measured improvement justifies them |
| Redis | No current implementation | Add only for a measured need such as shared rate limits across API workers |

Redis can run locally, but it would still be another managed process. It does not remove the need for relational business queries, FTS search or a certified catalog. A Redis-only redesign would also need explicit decisions about persistence, recovery, memory pressure and expiration. Redis documents distinct RDB/AOF durability tradeoffs; its existence alone does not establish durable governance storage. [Redis persistence](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/).

If Redis is later introduced, keep its scope narrow: atomic shared rate limits or explicitly temporary state. Use a local/private listener, restricted credentials and ACLs, bounded memory and TTLs, approved transport protection, and defined failure behavior. Cache keys must include the authorization scope and relevant catalog/policy versions; cached content cannot bypass current authorization. Avoid caching financial query results until owners define freshness and access-change behavior. [Redis security](https://redis.io/docs/latest/operate/oss_and_stack/management/security/).

**What is sound and should stay**

- Domain contracts are Pydantic models; transport delegates the chat flow to application services. A framework rewrite or microservice split would add cost without evidence of benefit at this load.
- Browser `user_id` is a consistency check, not identity. Plans, model text and metadata cannot grant access. Tenant, region/scope and metric grants are enforced again during planning and SQL validation.
- The compiler binds values and maps certified identifiers. Execution accepts signed capabilities rather than arbitrary SQL. Raw model SQL fallback is disabled.
- Monetary fixtures use integer minor units; formatting uses Decimal strings. Oracle precision/scale and certified metric units are explicit.
- The governed runtime pins a complete bundle, drains retired leases, rejects stale publication, and blocks rollback that would restore old grants. These are valuable controls, not unnecessary complexity.
- Metadata discovery produces physical evidence. It does not invent business certification or authorize access. Refresh runs outside API workers and does not auto-publish.
- Optional vectors, graph servers and additional model infrastructure are not required by the current architecture. Keep that restraint.

**Must fix before restricted office use**

1. **Recheck current authorization on session responses.** Evidence: `backend/nl2sql/api.py:343`, `api.py:348`, `runtime_bundle.py:377`.
   - **What this is:** Governed chat rechecks identity before and after its work. Session list/history routes directly use SessionStore after the initial authentication dependency.
   - **Problem:** Revocation between authentication and the history response is not checked again. A controlled synthetic API reproduction revoked the identity during the history read; the endpoint still returned HTTP 200 with result rows. This is a response-boundary gap, not evidence of a cross-user ownership bypass.
   - **Fix:** Put session operations behind a use case that checks current identity/policy around reads and before returning protected output. Use the governed runtime's current-policy guard and add a publication-during-history regression test.
   - **If we skip it:** A request that overlaps revocation can disclose historical results even though governed chat would reject the same stale identity.

2. **Apply access-change redaction to session titles.** Evidence: `backend/nl2sql/sessions.py:86`, `sessions.py:111`, `sessions.py:127`.
   - **What this is:** Titles are the first 100 characters of the user's question. Messages carry a scope digest and are redacted when current grants differ.
   - **Problem:** Session listings return the original title without a scope check. The synthetic reproduction confirmed that changing metric grants hides history content but still lists the original question title; a question could contain a customer name or financial threshold.
   - **Fix:** Store the title's authorization digest and use a generic title after grants change, or use generic titles from creation. Keep the existing response keys and the UI content unchanged.
   - **If we skip it:** The sidebar can reveal old question text that the history endpoint deliberately hides after an access change.

3. **Implement actual retention and an expiry-safe deletion path.** Evidence: `backend/nl2sql/sessions.py:97`, `sessions.py:111`, `sessions.py:202`; `docs/OPERATIONS.md` already acknowledges that physical purge is absent.
   - **What this is:** The retention setting filters expired conversations from reads and lists.
   - **Problem:** It never removes expired rows. A synthetic session dated 60 days ago retained its session and both message records; calling delete returned SESSION_NOT_FOUND because delete first calls the expiry-enforcing state method.
   - **Fix:** Add a bounded maintenance purge outside API workers, with an approved retention policy and backup treatment. Authorize deletion by owner separately from whether a session is eligible for reading; verify deletion behavior for expired sessions.
   - **If we skip it:** Sensitive history and database size accumulate, and users cannot delete expired history through the current endpoint. Ordinary SQL deletion also does not establish secure erasure from WAL files, backups or storage media.

4. **Finish corporate identity and credential lifecycle integration.** Evidence: `backend/nl2sql/auth.py:14`, `auth.py:28`; `backend/nl2sql/config.py:18`.
   - **What this is:** Current authentication supports locally configured opaque bearer hashes and locally verified HS256 JWTs. JWTs check signature, issuer, audience, time claims and subject, then resolve grants on the server.
   - **Problem:** Opaque tokens have no expiry/revocation identifier in TokenGrant. Corporate sign-in, account disablement, MFA, key rotation and enterprise token validation are not implemented by this local adapter; changing a local configuration file does not itself refresh a running legacy authenticator.
   - **Fix:** Use the organization's approved identity provider or gateway, validate tokens intended for this API, map stable identities to current server-owned grants, and define disablement/rotation behavior with a measurable revocation delay. Keep local demo credentials confined to synthetic use. Standard token validation requirements are defined by [OpenID Connect Core](https://openid.net/specs/openid-connect-core-1_0-18.html).
   - **If we skip it:** A stolen long-lived demo bearer can continue impersonating its principal, and corporate account lifecycle changes will not automatically become application enforcement.

5. **Provision restricted storage outside synchronized source folders.** Evidence: workspace path is under OneDrive; `backend/nl2sql/config.py:38`, `metadata_store.py:87`, `.gitignore`, and `config/office.example.json` use local/relative paths and markers.
   - **What this is:** Git ignores private files and metadata storage creates a .metadata-private marker. These protect source export conventions, not the Windows security boundary.
   - **Problem:** The application does not establish Windows ACLs, disable cloud synchronization or provision encryption. Launching with relative storage paths beneath this checkout can place runtime files under the OneDrive tree; actual synchronization and permission settings were not inspected.
   - **Fix:** Select approved, non-synchronized runtime paths; provision a dedicated OS identity, restricted permissions, approved encryption and protected secret injection. Verify the effective paths and ACLs on the office machine. Use SQLite-consistent backup procedures rather than treating file synchronization as database replication.
   - **If we skip it:** Private metadata, history or credentials can inherit unsuitable access or synchronization settings. SQLite requires reliable coordination of its database and WAL files; the OneDrive residency concern is an inference from the actual directory layout, not proof that any upload occurred. [SQLite WAL](https://www.sqlite.org/wal.html), [SQLite corruption guidance](https://www.sqlite.org/howtocorrupt.html).

6. **Separate enterprise approval verification from signing authority.** Evidence: `backend/nl2sql/governance.py:41`, `governance.py:137`, `metadata_config.py:54`, `managed_resources.py:68`.
   - **What this is:** The local approval adapter verifies HS256 signatures using reviewer secrets loaded into the application process. It checks coverage of physical, business and security roles.
   - **Problem:** Those symmetric verifier keys can also sign approvals. One configured reviewer may hold all roles; separate people and a separate publisher are not enforced. These are documented local-adapter limits, not a demonstrated signature bypass.
   - **Fix:** Before enterprise use, adopt approved asymmetric verification or an external approval verifier, keep signing keys with reviewers, and enforce the required separation of duties. Define key rollover and trust-revocation behavior for running processes, not only restart/recovery.
   - **If we skip it:** Compromise of a verifier process exposes approval-signing capability, and a three-role record may be mistaken for three independent approvals.

**Should fix**

7. **Bound saved history by total bytes.** Evidence: `backend/nl2sql/sessions.py:127`, `sessions.py:152`; `backend/nl2sql/api.py:348`; `backend/nl2sql/config.py:52`.
   - **What this is:** Each assistant message can save its result rows. History reads and deserializes up to 200 messages, then returns them together.
   - **Problem:** The query byte limit applies per execution, not to a whole conversation/history response. With 100 near-limit assistant results, default settings can retain and return roughly 100 MB of result payload before object and serialization overhead; this is a static upper-bound scenario, not a measured load result.
   - **Fix:** Enforce a total conversation byte budget and bounded history reads before deserialization. Set a smaller retained-result budget while preserving current response keys; defer a new pagination contract until the existing UI owner authorizes it.
   - **If we skip it:** A valid long conversation can consume substantial laptop memory and produce a slow, oversized history response despite passing every individual query limit.

8. **Make the request deadline cover session writes.** Evidence: `backend/nl2sql/sessions.py:65`, `sessions.py:86`, `sessions.py:152`; `backend/nl2sql/service.py:322`, `service.py:401`.
   - **What this is:** Session locking calculates remaining request time. SQLite also has a fixed connection timeout.
   - **Problem:** With an expired deadline, an uncontended lock can still be acquired with timeout zero and the write proceeds. The synthetic reproduction created a session with REQUEST_DEADLINE already expired; the fixed SQLite busy wait can also exceed a short remaining budget.
   - **Fix:** Reject expired deadlines before acquiring a lock and again before writes; bound storage waits by the remaining time and check before final persistence/response. Add a focused expired-deadline and contention test.
   - **If we skip it:** Requests can write state and finish after the advertised time budget, especially under storage contention.

9. **Keep rate limits consistent before adding workers.** Evidence: `backend/nl2sql/api.py:180`, `api.py:223`.
   - **What this is:** Each create_app call owns an in-memory dictionary of per-user request windows.
   - **Problem:** Separate API processes have separate counters, and restarts clear them. For example, two workers each enforcing 60 requests per minute do not enforce one aggregate 60-request quota.
   - **Fix:** Keep one process initially. If multiple workers are required, implement a shared atomic limiter, for which local Redis is a reasonable option, and test concurrent increments, expiry and store-failure behavior.
   - **If we skip it:** Adding workers silently changes the resource-protection policy. Redis is useful at that point; it is not currently necessary to make the single-process limiter work.

10. **Use one effective resource-budget contract.** Evidence: `backend/nl2sql/config.py:48`, `database.py:86`, `oracle.py:170`, `oracle_factory.py:16`, `oracle_factory.py:106`, `runtime_bundle.py:96`.
   - **What this is:** Planning exposes configurable join limits; the Oracle adapter has separate pool, timeout and result-byte settings.
   - **Problem:** Planning permits six join edges while both executors reject more than five. Also, changing general pool_size/query_timeout_seconds/max_result_bytes does not configure Oracle's separate NL2SQL_QUERY_ values; operators can believe a stricter limit applies when a different Oracle limit is effective.
   - **Fix:** Reconcile the advertised and executable join ceiling. Pass an explicit effective budget into each adapter, with documented backend-specific overrides, and test the selected limits without acquiring a corporate connection.
   - **If we skip it:** Some accepted plans cannot execute, and office tuning or safety limits can differ from operator expectations.

11. **Measure HTTP load and session contention before choosing infrastructure.** Evidence: `backend/nl2sql/load_evaluation.py:24`, `sessions.py:47`, `reports/concurrency.json`.
   - **What this is:** The existing benchmark calls the application service directly with disabled inference and synthetic SQLite. Session writes share a locked connection.
   - **Problem:** The saved untraced report shows about 158 ms p95 at ten callers and 1,470 ms at fifty, with about 1,423 ms p95 session-queue time at fifty. Its own flags say network_load_measured=false and real_model_or_oracle_qualified=false; those numbers do not establish office HTTP or real-model capacity.
   - **Fix:** Measure sustained authenticated HTTP traffic, long sessions, same-session conflicts and overload on office hardware, then repeat with approved model/Oracle fixtures. Tune retention, transaction work and admission limits before selecting a replacement history store; do not disable durability to improve a benchmark.
   - **If we skip it:** The team may size the service from the wrong workload or add Redis while the durable session-writing path remains the bottleneck. The saved measurements are historical evidence and were not rerun during this review.

12. **Add a protected security audit trail for reads and denials.** Evidence: `backend/nl2sql/api.py:223`, `api.py:245`, `api.py:322`; `backend/nl2sql/metadata_store.py:279`.
   - **What this is:** Current logs provide safe request correlation, status and stage timings. Metadata lifecycle events separately record administrative actions.
   - **Problem:** Analyst access logs do not record a protected actor reference and decision code sufficient to answer who accessed which governed report or was denied. Failed authentication exits before the authentication-success event, and the typed chat alias has less pipeline logging than the legacy route.
   - **Fix:** Emit one structured security event at the use-case boundary for allow/deny, session access and report execution. Include a protected actor reference, action, decision code and bundle/policy/query reference, with approved audit retention; exclude prompts, rows, raw SQL, binds and bearer tokens.
   - **If we skip it:** An incident investigation can correlate a request but may not reconstruct the actor, authorization decision and governed report consistently.

**Qualification decisions outside the code findings**

- Local operation is not the same as an offline application. The retained index.html loads Bulma and Font Awesome from public CDNs. The UI owner must validate the actual office copy's approved asset hosting; this review changed no UI bytes. Private HTTP inference and office Oracle also remain network dependencies when enabled.
- The current model defaults disabled. Exact templates and supported follow-ups work without it; the build is not evidence that a real Gemma model understands arbitrary business questions. Select an already approved local/private runtime only after a held-out accuracy, refusal, latency and memory evaluation. No weights were downloaded.
- Real Oracle qualification must prove grants, policy/context apply and reset, pooled cleanup, cancellation, NUMBER/DATE/TIMESTAMP behavior and approved golden results. Contract fakes do not establish any of these properties against a real server.
- Define business freshness separately from schema drift. Current answers explicitly say source refresh time is unknown; catalog default dates are not an enterprise freshness feed. Decide whether unknown/stale data is acceptable per report, then supply approved source timestamps and enforcement where required.
- Keep the flat package for now. If a Redis session adapter is actually justified, first introduce a small SessionRepository protocol because service.py and ports.py currently name SessionStore directly. Avoid reorganizing dozens of files solely to make the tree look more layered.
- Establish process supervision, backup/restore drills, disk-full handling, dependency/license review and laptop sleep/restart behavior before service use. A laptop is an intentional single point of failure unless the operating model provides otherwise.
- Prepare an approved offline installation bundle if disconnected installation is required. The current setup obtains packages through pip and does not provide a tested offline wheelhouse. No new dependency was added during this review.

**UI cleanup completed**

The retained copy is `UI/NL2SQL_V4_2_EXISTING_UI_BACKEND_ONLY_2026-10-16/existing_ui_reference/`. Before deletion, index.html, script.js and style.css in both locations were verified byte-identical. The canonical copy retains ASSET_SHA256.json and the original provenance README. The unique 319-line stt-frontend.test.mjs was moved unchanged into its tests directory; its relative script reference still works.

| Retained asset | SHA256 |
|---|---|
| index.html | ec90cc50d0736b54abda0a2ead19ae8f1156f8356543f3759b68164e9fa81033 |
| script.js | f31f4d08784f63be678d6f58d12709b15ddf0d69ecde3ad2c1521765f09b05ea |
| style.css | 4c3796c173fcb07ee0598adc4ceaba60519ae8e3a0f63a1e5349c7f5ede5077d |

Current architecture/configuration/operations documents and AGENTS.md were updated to identify the sole canonical copy and the local Redis decision. The historical numbered DESIGN_REFERENCE and historical evidence reports remain intact. No backend implementation fixes, browser integration, corporate connection, deployment or publication were performed.

**Verification**

- Mandatory `python scripts/check.py`: completed successfully, including pre-commit. Ruff check/format passed; Pylint 10.00/10; strict Pyright had zero errors/warnings; 346 tests passed, with 89% combined statement/branch coverage.
- Existing UI manifest preservation test: passed after duplicate removal.
- Retained JavaScript contract test: 16 passed through Node's VM-based test runner; no browser was opened.
- `git diff --check`: passed.
- Temporary synthetic reproductions confirmed history response revocation, title-redaction inconsistency, expired rows retained on disk, expiry blocking deletion, and an expired request deadline still allowing a session write. These were audit probes, not committed regression tests or fixes.
- Automatic command review rejected cleanup of the first synthetic audit temporary directory with "blocked by policy" and supplied no more specific reason. That temporary directory is outside the project; the requested duplicate UI deletion completed successfully. Subsequent probes cleaned their temporary directories normally.
- The test environment emits one Starlette warning about future TestClient HTTPX compatibility. The suite still passes; follow the approved dependency-upgrade workflow rather than adding an unapproved library solely to hide the warning.

Verdict: The governed compiler and metadata architecture is a sound synthetic foundation. Fix session authorization/retention first, then complete office IAM, storage and real-provider qualification. Keep the initial deployment local and simple; Redis is optional future infrastructure, not a prerequisite or a replacement for the entire storage design.

Lean: -1,405 duplicate UI asset lines, -0 dependencies. The unique test was retained.

Not checked: the actual office laptop or office UI copy, live corporate SSO/Oracle, installed Gemma/encoder/FAISS behavior, browser integration, real HTTP load, filesystem ACLs/encryption/sync state, backup recovery, or a fresh external vulnerability scan. Source review concentrated on the request, identity, session, compilation, execution and publication paths; it was not a line-by-line inspection of every optional evaluation helper or a live penetration test.
