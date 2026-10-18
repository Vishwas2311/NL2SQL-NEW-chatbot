# Current architecture and limits

Synthetic-first FastAPI backend with immutable Pydantic contracts, application
services, and typed adapters. Authentication and current server-side grants
scope retrieval, typed planning, deterministic SQL compilation, independent
validation, and read-only execution. Browser `user_id`, metadata text, and model
output cannot grant permissions. Raw SQL fallback remains disabled.

One runtime bundle pins the approved catalog, graph, retriever, compiler,
validator, policy, and execution resources for each request. Money uses exact
minor units or declared Oracle precision/scale and returns Decimal strings.
The supplied HTML/CSS/JavaScript UI and both reference copies remain frozen.

## API and source layout

The public compatibility surface is `/ews-chatbot/chat` and the owned session
list/load/delete endpoints; typed internal aliases are under `/api/v1/`.
Requests use synchronous JSON. Responses do not expose SQL, schema, or binds.
Speech returns an authenticated 501; export, result pagination, and cancellation
jobs have no implemented product surface.

- `backend/nl2sql/`: domain, catalog, retrieval, planning, compiler, security,
  auth, sessions, API, provider adapters, and metadata lifecycle.
- `metadata/synthetic/`: fictional approved catalogs and fixtures.
- `tests/`: security, SQL goldens, adapter, API-contract, and lifecycle tests.
- `scripts/`: mandatory checks and reproducible synthetic benchmarks.
- `reports/`: machine-readable measurements; historical Markdown reports were
  removed during documentation cleanup.
- `frontend-reference/` and `UI/*/existing_ui_reference/`: frozen UI.

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
edges must hold. JoinGraph emits NetworkX edges only for certified catalog relationships after
reconciliation succeeds. Edges retain pairs, cardinality, temporal rule, evidence and catalog version.

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
Filter depth/leaves and IN lists remain bounded. SQLite retains its stricter preflight checks.
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

Default: exact aliases, scope-partitioned SQLite FTS5/BM25 and NetworkX. Search documents derive
from certified labels/aliases/definitions/domain, approved table/column descriptions and view IDs.
Only metric-granted metadata enters each partition. Customer rows are never embedded.

EmbeddingProvider injection builds versioned vectors with dimension/finite-value and cumulative
memory checks. Hybrid lexical/cosine rank fusion falls back to lexical after safe encoder failures.
Catalog, source/domain, metric IDs, grant partition and backend accompany vector entries.

FaissVectorIndex implements approved lazy normalized IndexFlatIP and is wired through Retriever,
BundleBuilder and RuntimeFactory via vector_factory. Backend identity enters the artifact manifest.
FAISS and NumPy have NOT been installed or executed. A fake native binding tests approval-before-
import, array shape/dtype, normalization, dimensions and permissions. This is adapter evidence only.
No approved encoder or actual hybrid benchmark exists; lexical remains default.

Qualification requires the same versioned encoder/vector_factory in the builder and runtime, the
paired workflow evaluation, business-result/rejection/latency/memory comparisons and signed review.
No command downloads a model or silently enables vectors. Optional dependencies need approval.

Official reference: [FAISS exact indexes/cosine normalization](https://github.com/facebookresearch/faiss/wiki/Faiss-indexes).
Local measurements: reports/benchmark.json, reports/retrieval.json, reports/schema-evolution.json.
Scripted/toy evidence is explicitly distinct from real model accuracy.

## Release qualification

Local synthetic checks do not qualify company Oracle, corporate identity,
real Gemma/private or hosted inference, an installed encoder, or native FAISS.
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
