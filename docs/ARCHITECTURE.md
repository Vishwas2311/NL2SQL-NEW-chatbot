# Current architecture and limits

Start with the [verified system walkthrough](APP_WALKTHROUGH.md) for the current end-to-end
explanation, corrections to the older supplied architecture, database responsibilities and
three workflows. It distinguishes implemented adapters from qualified office services.

See the [application architecture diagram](ARCHITECTURE_DIAGRAM.md) for the
source-verified Azure-style overview, scalable SVG, high-resolution PNG and
editable draw.io source. Optional office integrations are explicitly marked.

Synthetic-first FastAPI backend with immutable Pydantic contracts, application
services, and typed adapters. Authentication and current server-side grants
scope retrieval, typed planning, deterministic SQL compilation, independent
validation, and read-only execution. Browser `user_id`, metadata text, and model
output cannot grant permissions. Raw SQL fallback remains disabled.

One runtime bundle pins the approved catalog, graph, retriever, compiler,
validator, policy, and execution resources for each request. Money uses exact
minor units or declared Oracle precision/scale and returns Decimal strings.
The supplied HTML/CSS/JavaScript UI remains frozen in one canonical reference copy.
On 2026-10-20, the user requested deletion of the byte-identical duplicate under
frontend-reference/. Its unique test was moved unchanged beside the retained assets.

## API and source layout

The public compatibility surface is `/ews-chatbot/chat` and the owned session
list/load/delete endpoints; typed internal aliases are under `/api/v1/`.
Requests use synchronous JSON. Responses do not expose SQL, schema, or binds.
Speech returns an authenticated 501; export, result pagination, and cancellation
jobs have no implemented product surface.

- `backend/nl2sql/domain/`: immutable business, physical, session and lifecycle contracts.
- `backend/nl2sql/application/`: chat/metadata use cases, typed ports, planning,
  deterministic SQL compilation and independent validation.
- `backend/nl2sql/infrastructure/`: authentication, databases, sessions, metadata
  repositories, retrieval, inference and Redis adapters.
- `backend/nl2sql/api/`: FastAPI routes, schemas, middleware and compatibility mappings.
- `backend/nl2sql/bootstrap/`: resource composition, runtime bundles and worker factories.
- `backend/nl2sql/cli/`: administrative and service entry points.
- `backend/nl2sql/evaluation/`: fictional fixtures and evaluation harnesses.
- `metadata/synthetic/`: fictional approved catalogs and fixtures.
- `tests/`: unit, contract, integration, security, evaluation and tooling groups.
- `scripts/`: mandatory checks and reproducible synthetic benchmarks.
- `reports/`: sanitized measurements and dated reviews; raw quality-console logs
  and the duplicate dependency-audit report stay local and are excluded from Git.
- `UI/*/existing_ui_reference/`: sole frozen UI reference, original hash manifest,
  and retained JavaScript contract test.

See [Code structure](STRUCTURE.md) for ownership and enforced dependency rules.

## VM concurrency and Redis

The user confirmed a VM with concurrent users and an existing Redis service on
2026-10-20. This supersedes the earlier single-process recommendation. The concurrent VM
template requires Redis and defaults to two workers. The office laptop template now uses
one worker, eight overall chat slots and one inference slot for initial qualification
on the upgraded machine. Neither profile
is a measured capacity claim.

RedisRateLimiter implements one atomic Lua rolling-minute decision using Redis's
clock, a namespaced hash of tenant/subject, unique request members, and 60-second
key expiry. It shares quotas across worker processes. Timeouts and connection
counts are bounded, command retries are disabled, and Redis failure returns a safe
503 without local fallback. Startup and readiness check Redis. Authentication and
current permissions remain independent of Redis; no query results are cached.
Both chat routes also acquire one atomic global/per-principal Redis lease around
the complete chat use case. Defaults are eight active chats across workers and one
per tenant/subject; these are provisional resource budgets, not user-capacity claims.
Crashes leave a lease that expires after 300 seconds. Unique lease IDs prevent an
expired request from releasing a newer request's slot. Normal and exceptional exits
release their own slots. Lost/expired admission prevents a successful chat response.
Rate admission and active admission are separate; even active-limit rejections
consume the authenticated request-rate quota. Session reads do not occupy chat slots.
Leases must outlast request and Redis I/O budgets. They do not forcibly terminate a
hung driver or model call, and Redis loss/restart is not strict physical resource
fencing. Drain API work before planned Redis maintenance and retain provider-side
timeouts/pools. No heartbeat scheduler or background job system is introduced.
Readiness verifies authentication, scripting and required sorted-set commands in
an isolated, expiring probe key, rather than relying only on PING. The check-redis
CLI uses the same adapter without opening Oracle, inference or application databases.
The redis-py optional dependency is pinned in requirements-redis.lock and the
development lock. The office VM Redis service is not installed or deployed here.
An optional loopback-only Docker Compose service and generated least-privilege
application/test ACLs support real local synthetic qualification. Generated .env
and test credentials are ignored; they are not office secrets or deployment files.

The supported `python -m nl2sql serve --workers N` launcher uses an importable
application factory, so spawned workers independently load the same selected JSON,
dotenv and process environment. Configuration rejects more than one worker with
the memory limiter. HTTP connection/task admission is bounded per worker.
The API remains loopback-bound for an approved same-VM reverse proxy; no proxy,
corporate sign-in, TLS termination, UI hosting or deployment is performed here.

Synthetic query data and durable sessions retain separate SQLite databases, and
governed metadata retains its private transactional SQLite repository. All workers
on one VM must share the same approved local paths; SQLite compare-and-swap and
metadata publication leases protect cross-process changes. Network-share databases
and multi-node operation remain unqualified. Redis does not resolve session-writer
contention or establish business-query capacity. Per-worker pools, indexes and model
clients consume resources independently; total database connections multiply by
worker count and must be approved and load-tested.

Single-process synthetic development still defaults to the memory limiter and
does not require Redis. The real-server Redis suite uses only an explicit local
NL2SQL_TEST_REDIS_URL and has a dedicated CI service. Contract fakes alone do not
qualify Lua execution or VM Redis connectivity.
Real local qualification now includes two spawned API worker processes serving
HTTP, shared quotas, active leases and exact synthetic results with durable history.
The supplied CI job runs these tests against a real standalone Redis service.

Session routes delegate to application SessionService, rechecking current identity
before and after persistence operations. Governed identity refresh observes new
publications; a revocation during a history/list read blocks the response. Public
titles are generic to avoid disclosing question text after grants change. Saved
messages continue to redact when their authorization digest differs. History has
a four-million-byte UTF-8 budget per conversation and a 200-message limit; reads
reject oversized legacy histories before materializing their message payloads.
Owner-bound deletion works after expiry. An explicit bounded purge-sessions CLI
removes expired sessions and cascaded messages outside API workers. No automatic
session-purge scheduler, backup purge or secure physical-erasure guarantee is implied.
Session operations reject an already expired request deadline and bound SQLite
writer waits to the remaining budget, so a free Python lock cannot admit a late write.
Messages have a session/id index for ordered history reads and cascaded deletes;
the index is created idempotently for existing synthetic stores at startup.

Local backend operation does not establish a fully offline application: the frozen
UI references public CSS/icon CDNs, provider settings permit explicitly approved
network endpoints, and the office Oracle source is external to this laptop.
Inference defaults disabled. Runtime data must use approved restricted storage
outside cloud-synchronized source folders; actual sync settings and ACLs require
office verification. The dated reports/application-architecture-review-2026-10-20.md
records the earlier baseline. The 2026-10-21 follow-up adds real Redis connection
qualification, active-chat admission, session response reauthorization, generic
titles, byte budgets and bounded retention cleanup. Enterprise IAM, protected
storage, backup policy and actual provider/VM qualification still remain open.
See the [current quality review](../reports/redis-and-code-quality-review-2026-10-21.md)
for the implemented fixes and remaining release gates.

## Implemented metadata contracts

### Discovery design

MetadataDiscoveryProvider.discover returns immutable PhysicalInventory. OracleDiscovery is the
authorized office adapter. SyntheticDiscovery and FileDiscovery exercise the same staging contracts.
Copied Oracle JSON requires live reconciliation; possessing an offline file cannot certify a live schema.

Approved-environment, owner and network flags are checked before acquiring a connection. Discovery
credentials are SecretStr environment settings, separate from business-query credentials. Owner
values are bound and SQL projections fixed. Business rows, default expressions and statistics are
not fetched. Cumulative row/byte/deadline budgets, a read-only transaction and rollback/release/drop
cleanup apply. Routine diagnostics use safe codes.

The workflow discovers, fingerprints, classifies, computes dependencies, reconciles semantics, builds
compatible artifacts and stores a pending immutable candidate. Physical-only bootstrap remains
useful without semantics but cannot publish. Gemma never detects schema changes.

Official references: [ALL_TAB_COLUMNS](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/ALL_TAB_COLUMNS.html),
[ALL_CONSTRAINTS](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/ALL_CONSTRAINTS.html),
[python-oracledb connection API](https://python-oracledb.readthedocs.io/en/latest/api_manual/connection.html).
Actual corporate privileges and versions require DBA qualification.

### Physical inventory

The local fixture contains five fictional tables: regions, customers, loans, accounts and payments.
SyntheticDiscovery reads sqlite_master and PRAGMA column/PK/unique/FK/index metadata through a
read-only connection. It never samples business rows. Daily amounts do not enter schema fingerprints.

OracleDiscovery reads bound, allowlisted owners against ALL_TABLES, ALL_VIEWS, ALL_TAB_COLUMNS,
ALL_CONSTRAINTS, ALL_CONS_COLUMNS and ALL_OBJECTS. Optional ALL_INDEXES, ALL_TAB_COMMENTS,
ALL_COL_COMMENTS, ALL_DEPENDENCIES and ALL_VIEWS.TEXT_VC enrich evidence. No company database
was contacted.

PhysicalInventory preserves raw owner/name/type, precision, scale, length, nullability, ordered key
pairs, referenced owner/constraint, validation status, comments, dependencies and DDL timestamps.
Canonical IDs combine a safe normalized stem and a hash of case-preserving raw identifiers.
Owner-qualified physical names remain separate from internal IDs.

Missing required visibility fails closed. Optional failures are recorded. Invalid objects, invisible
target keys, missing definitions and views exceeding bounded TEXT_VC evidence remain pending.
Names/comments cannot certify a join, amount meaning, tenant rule, currency or permission.

Detailed payloads live in private marked storage. This document contains synthetic names only.
There is no corporate inventory or claim of corporate schema coverage.

### Relationship evidence

Synthetic keys are extracted from SQLite metadata. Oracle uses ordered ALL_CONS_COLUMNS and
ALL_CONSTRAINTS P/U/R records. A foreign key requires an enabled, validated referenced key within
approved visibility. Unknown targets remain unverified.

Reconciliation matches semantic relationships to exact physical objects and complete key mappings.
Target unique grain, compatible types, tenant partition pairs and source uniqueness for one-to-one
edges must hold. Bootstrap projects certified catalog relationships into LadybugDB after reconciliation.
The catalog and JoinGraph policy evidence retain full key pairs, cardinality, temporal rules,
review references and version identity. Native links retain topology/relationship IDs and lineage;
the graph projection does not become a separate business or access authority.

The fixture has loans -> customers, accounts -> customers, payments -> customers and customers ->
regions. Composite joins include tenant_id; customer IDs overlap between tenants. Historical use
of current-only attributes is refused. Multi-fact reports aggregate facts before combining them.

Discovery adds no executable edge. Missing, ambiguous, fanout, incomplete composite and unverified
relationships reject. Path search stops after two paths. Effective-dated/SCD2 interval joins remain
unsupported until a certified temporal contract and compiler extension exist.

### Business mappings

Certified metadata declares metric ID, aliases, definition, source table/column, aggregate, temporal
kind, currency/unit, divisor scale and output decimal places. Discovery cannot invent these meanings.

Loan exposure uses SUM(amount_minor)/100; loan count uses COUNT(loan_id); average exposure returns
exact sum/count before Decimal formatting. Account/payment measures retain their own native grains.
Difference/percentage expressions reference compatible approved primitive sums. All records are fictional.

Oracle Column.kind=decimal maps known NUMBER precision/scale; integer requires integral storage.
A major-unit currency declares scale=1; minor-unit currency declares its divisor. decimal_places
governs output precision. NUMBER(38,6), USD major units and six-place output are tested through an
injected driver, including a 38-digit value. Money never uses a binary float.
Compiler bind scaling and independent filter verification use an explicit Decimal precision,
so the process's default 28-digit context cannot round an approved threshold.

Changed aliases, sources, formulas, units, scales, views, time rules or grants need signed review.
Metadata text and model output cannot confer permissions. New metrics need explicit grants before
retrieval or execution. No corporate business mapping has been approved.

### Certified view coverage

| Synthetic view | Semantics | Policy |
|---|---|---|
| loan_snapshot | Loan-grain dated snapshot | Tenant, allowed region, active status |
| account_current | Current accounts only | Tenant, allowed region, active status |
| payment_events | Events within ISO/fiscal bounds | Tenant, allowed region, active status |
| customer_portfolio | Independently preaggregated facts at customer grain | Component and outer scope |

ScopePolicy maps tenant column, scope dimension, protected regions/scopes claim and optional status.
Oracle database_context requires separately approved read-only grants and DBA context apply/reset
procedures. SQLite cannot stand in for that policy. EntityMapping declares exact ID/label columns
and direct scope mappings. Numeric IDs are bound without comparing arbitrary labels to NUMBER.

Four synthetic views are covered. No corporate view is certified. Missing physical uniqueness or
incomplete definition evidence remains pending; approval cannot bypass reconciliation. Unsupported
operators and grain combinations reject explicitly.

### Typed SQL capability contract

Supported: certified multi-table/composite joins; multiple measures/dimensions; sum/count/min/max;
exact sum/count average; compatible differences/ratios/percentages; bounded AND/OR filters, NULL
tests and text IN; snapshots, event ranges and fiscal calendar bounds; GROUP BY/HAVING; deterministic
sort/limit; preaggregation CTE; independent multi-fact aggregates; ROW_NUMBER/DENSE_RANK/top-N.

SQLGlot maps internal IDs to quoted Oracle owner/object/column names. The independent validator
reverses approved mappings and checks the whole AST, policy, filter, time, grain, order and limit.
Recursive wrappers are checked independently. Raw SQL fallback/model SQL, unknown functions,
unapproved sources, incomplete keys and literal value insertion stay disabled.

Unsupported: arbitrary SQL/subqueries, general SCD2 interval joins, month/year-over-year operators,
RANK, LAG/LEAD, running totals and unrestricted window/expression syntax. Average/ratio HAVING
and sorting also reject explicitly. No verified company contract defines these added semantics;
they are not represented as implemented.

Settings can reduce max_metrics/max_dimensions (1..5), max_rows (1..1000), max_join_edges (0..6).
Filter depth/leaves and IN lists remain bounded. Both executors support the six-join ceiling and honor lower configured budgets.
Decimal-source execution and database-context policy require Oracle. Unit/divisor/output precision
are explicit. Native Oracle date/Decimal bind behavior is contract-tested without a live database.

### Versioning and approval

BundleSpec SHA256 binds inventory, catalog, current principals, artifact fingerprints, impacts and
creation time. Lifecycle status and signed evidence live separately in a private SQLite WAL store.
Source profiles store paths/source identity, never passwords.
The candidate also binds its base publication. Publishing after another activation requires restaging
and fresh review, preventing an older approval from undoing newer revocations. Changed policy
fingerprints require a fresh revision label and matching principal revisions, invalidating saved history.

Lifecycle: pending_verification or pending_approval -> certified -> published -> superseded, with
rejection/retirement. Physical verification is separate evidence. Imported catalog.approved=true is
not publication authority. Three configured roles (physical, business, security) and a separately
authenticated administrator are required. Protected environment keys authenticate local HS256
review/admin evidence. Manifests cannot nominate trust anchors or confer roles. Signatures bind the
candidate, source, reviewer and reference with issuer/audience/time checks.

demo-trust/sign-demo are explicit fictional-synthetic-only commands. They cannot certify company
metadata. Corporate SSO/key distribution, asymmetric-signing policy, external owner approval and
rotation need enterprise integration. Published review evidence may outlive token expiry; revoking
its configured key still blocks verification/recovery.

Publication checks signatures, live physical fingerprints, all artifact versions and runtime readiness,
then rediscovers for concurrent source changes. One transaction compares revision/active ID and
swaps the pointer. A bounded cross-process refresh lease fences expired workers.

Rollback requires a previously published, trusted, physically compatible version with security policy
and grants equal to current. It cannot restore older access. To revert semantics with newer grants,
stage a newly reviewed revision. Restricted storage/OS permissions remain deployment requirements.

### Drift classification

Normalized fingerprints omit observation time and business rows. They retain source identity,
owners, classification, verification, columns, keys, dependencies, definition digests and DDL evidence.
SQLite FK identities use endpoints/pairs rather than unstable PRAGMA sequence numbers.

Classes: compatible physical addition, metadata-only, approval-required addition, breaking physical,
breaking semantic, security-sensitive and unknown. Possible renames remain unverified. Type,
precision, nullability, removal, key, definition, policy and source changes are not assumed harmless.

DependencyGraph links tables -> columns -> relationships/dimensions/metrics -> views -> compiler/
saved-plan consumers, plus retrieval and policies. Physical breaks quarantine affected active views.
A missing account table blocks account/portfolio reports while dated loans still work. Proposed
semantic changes do not mutate active access.

Every candidate requires certification. Unmapped compatible additions retain approved semantics and
reuse artifact references. Row changes update answers without schema/index rebuild. Unknown or
incomplete evidence fails closed for dependent reports.

### Change impact matrix

| Change | Active behavior | Candidate/approval |
|---|---|---|
| Ordinary rows | Current authorized rows queried | No schema/index rebuild |
| New table/column/FK | No new metric, edge or permission | Pending review; unchanged artifacts reused |
| Comment/synonym | Approved meanings stay active | Reviewed retrieval update |
| Type/precision/nullability/key/removal | Dependent views quarantined | Reconcile before publication |
| View/metric/grain/time rule | Old semantics retained unless physically broken | Review and rebuild/check |
| Grants/policy | Current grants checked every turn/capability | Security review; rollback cannot restore access |
| Ambiguous/unverified join | Plan refused | Resolve evidence and grain |
| Graph/index/runtime failure | Active pointer/resources retained | Candidate never activates |
| Source change during activation | Transaction rejected | Rediscover and review |
| Lease expiry/CAS conflict | Stale worker rejected | Retry current revision |

Saved-plan consumers are invalidated by catalog/policy proofs; a separate enterprise report scheduler
is not implemented. Removed sources remain traceable through old mappings. Proposed grant changes
mark consumers for revalidation without disabling the currently approved bundle.

### Runtime consistency

RuntimeMetadataBundle retains one specification/catalog and matching compiler, validator, graph,
retriever, service and execution pool. RuntimeFactory prepares complete resources outside the swap
lock. Preparation failures close new handles and preserve active resources. Fingerprints/model
versions must match.

RuntimeManager reads a protected local publication pointer before pinning. Chat never queries Oracle
dictionary metadata. A request lease keeps one bundle through planning, validation, execution and
response authorization. Retired pools/indexes close after their final request. Shutdown drains leases.
Rollback to a still-leased version creates a separate lease identity to prevent double closure.

Capabilities include bundle version and principal digest. Guards check the durable pointer, current
grants, policy compatibility, quarantine and physical impacts. A worker observing another publication
fails closed until reload. Revocation during execution discards the response. History also uses current
grants and session ownership.

Unchanged catalog/grants/encoder partitions share a reference-counted retriever. Startup reconciles
physical metadata once; polling runs only in an explicitly enabled external process. Tests exercise
concurrent threads, separate repository connections, CLI processes and recovery. Distributed storage,
multi-node HA and production load are unqualified.

### Refresh operations

Scheduling defaults disabled. An authorized administrator configures 5..86400 seconds, initially with
--dry-run. A separate `metadata monitor` process atomically claims due work. `--once` runs one tick.
API workers never create poller threads. The laptop must remain on; no system service was deployed.

Refresh discovers -> compares -> impacts -> reconciles -> stages. It never auto-approves/publishes.
Retries default to one (ceiling two), only for discovery timeout/unavailability or contention, with
bounded backoff. Logs contain safe IDs/codes, not exception text, comments or credentials. A lease
prevents duplicate work and fences expired workers. Unaffected approved reports remain available.

For a new Oracle column: authorized sync --dry-run; inspect impacts; sync to persist; inspect the
private candidate. Owners decide whether it stays unmapped. For approved business use, supply a
revised semantic file and current grants file, obtain physical/business/security signatures, approve
and publish. Supported mapping changes need no Python rewrite. Unknown semantics need a certified
compiler extension rather than an inferred rule.

Disable scheduling for maintenance. Failed discovery retains the active bundle. A detected physical
break quarantines dependent reports until compatible reviewed publication. Rollback requires physical
compatibility and unchanged policy/grants. See [Operations](OPERATIONS.md) for commands.

### Index and graph report

Default: exact aliases, scope-partitioned SQLite FTS5/BM25 and LadybugDB. Search documents derive
from certified labels/aliases/definitions/domain, approved table/column descriptions and view IDs.
Only metric-granted metadata enters each partition. Customer rows are never embedded.

EmbeddingProvider injection builds versioned vectors with dimension/finite-value and cumulative
memory checks. Hybrid lexical/cosine rank fusion falls back to lexical after safe encoder failures.
Catalog, source/domain, metric IDs, grant partition and backend accompany vector entries.

FAISS/NumPy bindings and the unused vector-factory selection path have been removed.
A configured encoder automatically creates an embedded Ladybug exact-cosine projection
per authorized metric partition. Fixed-size DOUBLE arrays, finite nonzero normalization,
authorization predicates before limiting and serialized native cleanup are exercised with
real local Ladybug. No extension, HNSW dependency or vector server is installed. The
projection is rebuilt in memory at activation; an optional marked private encoder cache
retains compatible vectors. Per-partition native buffers multiply by API workers.

Qualification still requires the same versioned encoder and corpus in staging/runtime,
paired workflow evaluation, result/rejection/latency/memory comparisons and signed review.
No command downloads a model. Actual encoder semantic accuracy remains unqualified.
Official reference: [Ladybug array cosine similarity](https://docs.ladybugdb.com/cypher/expressions/array-functions/).
Local measurements: reports/benchmark.json, reports/retrieval.json, reports/schema-evolution.json.
Scripted/toy evidence is explicitly distinct from real model accuracy.

## Release qualification

Local synthetic checks do not qualify company Oracle, corporate identity,
real Gemma/private or hosted inference, or an installed encoder on the target Mac/VM.
No company connection, weights download, public publication, or deployment is
authorized by these guides.

Outstanding work requires approved Oracle dictionary/query identities, DBA
read-only grants and context apply/reset routines, real precision/date/cancel
tests, steward-certified business mappings and grains, corporate identity and
revocation, approved model/encoder evaluation on held-out data, and HTTP load
qualification. Freshness, startup reconciliation, scheduler ownership, restricted
storage ACLs, monitoring, backups, retention, multi-node operation, and final
security/privacy/license/release signoff remain organizational gates.

Ponytail guidance does not replace Ruff, Pylint, strict Pyright, coverage, or
pre-commit checks. Hook execution is not claimed without runtime evidence.
Run the checks in [Configuration](CONFIGURATION.md#operations-and-evidence)
before relying on current source behavior. Historical proposed capabilities are
kept separately in [Design reference](DESIGN_REFERENCE.md).


## Embedded graph migration (2026-10-23)

LadybugDB 0.21.2 is the selected local embedded runtime join topology store.
There is no graph database daemon, cloud connection, model call or extension download.
Bootstrap builds a catalog-digest-named file under `data_dir/graphs`, checkpoints and
closes its single writer, then exposes read-only handles to API workers. New versions
use different files. Runtime leases retain old handles until in-flight work drains.
SQLite remains the approval, grants, active-pointer and session authority.
Pure application adjacency performs structural catalog validation and drift impact;
this transient evidence is not another database or a runtime fallback.

`NL2SQL_GRAPH_BUFFER_MB` bounds each handle's native buffer pool (default 64 MiB,
32?1024 MiB). Native query threads are fixed to one per handle. Memory also includes
engine overhead, live bundles and search/compiler resources: this is not a process RSS cap.
`NL2SQL_GRAPH_NATIVE_DIR` optionally names an approved Windows DLL directory; never
point it at an untrusted/user-upload directory. The current Windows wheel requires
OpenSSL 3 DLLs. A wheel install alone does not establish native-load compatibility.

Graph creation uses a private temporary file and exclusive `.building` reservation.
Failures do not replace an existing graph. A stale reservation after process death
requires operator inspection and removal while builders are stopped. Never delete an
active graph or clean files based only on one worker's local lease count. Back up graph
files together with their approved catalogs; they are rebuildable projections.
Read-only startup verifies catalog identity and certified join records. Corrupt files
fail closed; restore/rebuild under maintenance rather than editing the active file.
Scheduling remains disabled by default and stages changes for review, never auto-certifies.

## Automatic preparation and SLM context protection (2026-10-23)

`metadata prepare` discovers/stages, verifies supplied signed review, publishes only
certified candidates and checks graph/search/vector/query resources automatically.
`office` orchestrates this before supervising separate API and monitor processes. It
explicitly enables the external schedule after preparation; bare API startup never does.
New physical objects remain evidence, not business/access certification. An absent catalog
can be discovered and staged without loading the synthetic fallback catalog. Changed backend
manifests require restaging/review of older bundles; obsolete fingerprints are never rewritten.

Metric grounding now expands authorized typed column/table/view BM25 evidence. Exact
aliases retain their fast route. Restricted HTTP planning requires the runtime's full-request
token counter, output reserve and configured context window. Optional rich records may be
removed once; required contracts cannot be clipped. Malformed/oversized counts fail before
generation. Private/TLS, same-origin and total deadline controls cover counting/generation.
The six-edge executor ceiling now matches planning, with lower configured budgets honored.
This is bounded supported planning, not a cost-based small/medium/large classifier.


## Architecture review remediation (2026-10-24)

The current composition remains a modular monolith. ChatService receives one immutable Catalog
and an explicit SQLValidator/executor pair; the unused CatalogProvider indirection and object-identity
snapshot check are removed. RuntimeManager still pins one complete approved bundle and rejects
revoked grants; no raw SQL fallback or independent SQL check was removed.

`application/routing.py` owns exact catalog templates and small deterministic follow-ups.
`application/results.py` owns exact Decimal row formatting. Synthetic report templates already
live in the fixture catalog; production routing contains no fallback report dictionary keyed by
synthetic catalog versions. Write-intent screening is anchored to command intent, not any occurrence
of words such as update. Typed DSL and read-only execution remain the actual execution safeguards.

`domain/planning.py` adds PlanningDecision, typed clarification and one pending-question contract.
Flexible follow-ups receive only compatible, currently scoped typed plan context. Clarification
choices are grounded before persistence and perform no database query. HTTP model response_format
contains the decision schema; it is not duplicated in default structured-mode metadata.

SQLite upgrades and payload readers are versioned, preserving legacy payload identities and actual
creation/discovery timestamps. Driver storage failures are translated by infrastructure. Domain
Failure carries a category; transport maps categories to the unchanged HTTP contracts. Both chat
routes use the same invocation/metrics boundary and inherited application deadline.

Retrieval preflights schema plus metric text and aggregate configured native buffers. Metadata
cache checkpoints are separate from query encoding and select metadata vectors explicitly. Redis
continues to coordinate admission only. The default office profile is lexical-only, with optional
approved private-HTTP embeddings and automatic vector preparation when enabled.

Office checks require protected absolute storage outside source/sync folders and patched native
SQLite. The stock launcher supports one worker; a qualified multiworker VM still needs Redis and
its approved supervisor. Twenty-identity HTTP burst tests use controlled synthetic planning and
verify bounded admission; they do not qualify real SLM throughput. macOS CI checks are defined but
have not been run by this Windows session. See the remediation report for verification and office gates.

## Separate inference admission (2026-10-24)

The outer API admission still spans the complete turn and enforces current global and
tenant/subject concurrency. `application/inference.py` holds a separate inner lease around
the model-provider call. Exact catalog templates and recognized deterministic follow-ups
bypass this inner lease; model-based follow-ups use it. Overall/database/session budgets
still apply to every route. A template can still be rejected when overall capacity is full;
there is no unconditional latency or reserved-capacity guarantee.

Bootstrap owns both admission lifecycles. All live catalog bundles in one process share the
same InferencePlanner and limiter; Redis uses separate keys to share the inference ceiling
across workers. Inner overload fails promptly with INFERENCE_CAPACITY/429. Leases release
on model success, typed clarification, malformed output or failure. A Redis release failure
does not authorize execution. Existing current-grant, capability and request deadline checks
remain independent. Publication probes use DisabledModel and never acquire model capacity.

Office examples target 100000 tokens with one inference slot. This is deployment intent,
not a claim of live model support, actual memory allocation or target-machine qualification.
