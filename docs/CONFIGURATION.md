# Setup and configuration

## Office laptop preparation (2026-10-24)

Use [the single Windows office installer](OFFICE_INSTALLER.md) for the complete CPU
embedding runtime, Oracle/Redis clients, quality tools and private connection profile.
`python3.13 setup_env.py --office` remains a smaller setup without local embedding packages.
Office setup checks the linked SQLite
library for the WAL-reset fix; Python 3.13 alone is insufficient. Use SQLite 3.51.3+
or the documented 3.50.7/3.44.6 maintenance backport. A pip dependency update does not
replace the standard library SQLite engine. Recreate the environment on macOS;
do not copy the Windows `.venv`. Native SurrealDB loading must be checked on the actual Mac.

Copy `config/office.example.json` to protected settings and change its storage paths to
approved absolute local paths outside OneDrive/iCloud/network shares. Its loopback model
ports are examples, not running services. Copy `config/office.env.example` separately
to a private environment file; the synthetic `.env` and two-worker VM profile are different
profiles. Set the exact model ID. Embeddings and disk snapshots default disabled; if
enabling hybrid retrieval, select its approved endpoint/identity or an existing local model
folder. The built-in local loader derives its dimension and immutable file identity.
The office profile uses one worker, eight overall chat slots and one inference slot;
these are provisional limits for the upgraded target machine, not a measured capacity claim.
the Redis VM profile remains available separately for qualified concurrent deployment.

The selected private `--env-file` now reaches application settings, Oracle discovery,
Oracle query accounts and reviewer trust. Precedence is actual environment > explicitly
selected environment file > JSON > defaults. No parent-directory dotenv is searched and
dotenv interpolation is disabled. Keep real secrets in the approved secret manager when available.

Restricted HTTP planning requires `model_token_count_endpoint` on the same origin as
`model_endpoint`. It receives the complete chat-completion body and returns
`{"input_tokens": 123}` using that runtime's tokenizer/chat template. The implementation
matches llama.cpp's documented `/v1/chat/completions/input_tokens` contract; other runtimes
must provide that contract or use a trusted provider adapter. The counter is not another
generation call. The application reserves `model_max_tokens` plus
`model_token_safety_margin` within `model_context_tokens`, removes optional rich evidence
once if necessary and rejects a request that still cannot fit. Byte limits remain an
additional bound. Synthetic mock HTTP tests without a counter do not qualify a real model.
See the [official server contract](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md#post-v1chatcompletionsinput_tokens).

With an approved embedding endpoint or registered installed local encoder, the application
automatically builds metadata vectors and embedded SurrealDB exact-cosine projections. FAISS
and its NumPy/native adapters have been removed. No extension, model download or vector
server is installed. Vectors use authorized metric partitions, never business rows. Native
vector projections are rebuilt in memory at activation; the optional protected encoder cache
persists vectors across restarts and bundle digests still verify compatibility. Admission estimates 32 MiB per live
vector partition; this is not a native allocator limit. Measure RSS across grant partitions,
retained bundles and API workers.
`index_storage_path` defaults null in the office example. If approved restart caching is
needed, select a marked private path. Metadata checkpoints run during preparation, outside
the encoding lock; ordinary question cache misses never rewrite the disk snapshot.
Checkpoints persist only the explicitly selected metadata hashes/vectors, not question vectors.

Use the office launcher described in OPERATIONS.md after configuring approvals and endpoints.
The launcher supervises monitoring outside API workers. Bare `serve` never starts a scheduler.


See [System walkthrough](APP_WALKTHROUGH.md) for how the selected query backend, embedded
SurrealDB graph, Redis admission and optional model/embedding adapters work together.
Selecting a provider does not establish live office qualification.

This is a synthetic Windows/Python 3.13 development build. Company Oracle, corporate identity,
real inference and installed embedding runtimes require separate qualification on the target Mac/VM.
Original numbered designs are consolidated in [Design reference](DESIGN_REFERENCE.md). UI assets are preserved.

The sole UI reference is `UI/*/existing_ui_reference/`; the byte-identical
`frontend-reference/` copy was removed at the user's request on 2026-10-20.
The retained HTML, JavaScript and CSS still match the original SHA256 manifest.
No UI integration or content changes were made.

Single-process synthetic development defaults to the memory limiter. The concurrent
VM profile requires the implemented Redis adapter; worker count and capacity still
need qualification on the target VM. For restricted office use, explicitly select
non-synchronized, company-approved `data_dir` and `metadata_root` paths; the relative
development defaults do not enforce ACLs or prevent cloud synchronization.

## Concurrent VM configuration

Install the pinned optional Redis client with the chosen Python environment:

```text
python -m pip install -r requirements-redis.lock
python -m pip install --no-deps -e .
```

The office Redis service must be supplied by the VM owner. The optional local
synthetic Docker service is described in OPERATIONS.md; it is not an office deployment.
The VM OS and expected simultaneous
user count have not been supplied; the factory launcher supports process spawning
without assuming Gunicorn or Docker. Use `.venv/Scripts/python` on Windows or
`.venv/bin/python` on Linux if the environment is not activated.

Select the protected settings file and `--env-file config/vm.env.example` when
serving. That template selects Redis and two workers, but deliberately contains no
Redis credential. Inject `NL2SQL_REDIS_URL` through approved process-environment
secret management. A loopback URL uses redis://; a non-loopback host must use
rediss:// with verified TLS. URL query overrides and fragments are rejected.
URL credentials must be percent-encoded by the secret provisioner. Redis Cluster
and Sentinel discovery are not implemented by this standalone-service adapter.

| Setting | Default / behavior |
|---|---|
| rate_limit_backend | memory for development; redis in the VM template |
| redis_url | SecretStr; required with Redis; no committed real credentials |
| redis_key_prefix | ews:nl2sql; use one deployment-specific prefix shared by its workers |
| redis_timeout_seconds | 0.5 seconds each for connect and command I/O; no command retry |
| redis_max_connections | 16 per API worker |
| redis_ca_bundle | Optional approved PEM CA file; allowed only with rediss://; certificate and hostname verification remain required |
| requests_per_minute | 60 per authenticated tenant/subject across the deployment |
| max_concurrent_chats | 8 active chat use cases across all workers |
| max_concurrent_inferences | 1 active model call across all workers; templates bypass this inner limit |
| max_concurrent_chats_per_principal | 1 active chat per authenticated tenant/subject |
| admission_lease_seconds | 300; must exceed request_timeout_seconds plus twice redis_timeout_seconds plus 5 seconds |
| api_workers | 1 for development; VM template 2; allowed 1..16 |
| http_concurrency_limit | 64 accepted connections/tasks per worker; tune with HTTP load |
| max_session_bytes | 4,000,000 UTF-8 bytes of serialized messages per conversation |

Each setting maps to its upper-case NL2SQL_ environment name. Shared limits apply
only to workers using the same Redis service/database and deployment prefix. Grant
changes do not reset a subject's rate counter or active slot. Both chat routes hold
outer slots through planning, execution and persistence; session routes use rate quotas
without taking chat slots. Active-limit rejections still count toward the rate quota.
Flexible planning takes a second slot only for the provider call, including token counting
and retries. There is no inference waiting queue. Its excess work receives
`INFERENCE_CAPACITY`/429 and `Retry-After`; all successful/exceptional exits release the slot.
One inference per tenant/subject is permitted. Redis inference leases use the same configured
backend and a separate `<redis_key_prefix>:inference` namespace. There is one shared inference
handle per API process, retained across catalog replacements. Each of the two Redis handles
has its own bounded connection pool; allow up to twice `redis_max_connections` per worker.
CHAT_IN_PROGRESS and CHAT_CAPACITY return 429. Redis failure returns 503; an expired
lease on completed work returns ADMISSION_EXPIRED/503. A lease is crash recovery,
not forced cancellation or a guarantee against Redis restart/eviction resetting state.

The CLI accepts `--workers N`; more than one worker with the memory limiter rejects
configuration. Use the provided CLI rather than specifying a different worker count
in an unrelated external Uvicorn command. Each worker loads the same explicitly
selected settings/environment paths through bootstrap.factory:create_configured_app.
CLI worker/metadata-root overrides are passed to child processes through process
environment. No plaintext settings or secrets are serialized into command arguments.

All workers on one VM must share the same approved local `data_dir`/`metadata_root`
and Redis namespace. Keep SQLite databases on a local volume, not an SMB/NFS share.
Database and Redis pools, in-memory indexes, and model clients are per process:
synthetic query connections are approximately workers times `pool_size`. Oracle uses
`NL2SQL_QUERY_POOL_MAX` instead; its query timeout/result budget likewise use
`NL2SQL_QUERY_TIMEOUT_MS` and `NL2SQL_QUERY_MAX_RESULT_BYTES`. Active/retiring bundles
can temporarily own separate pools.
Existing metadata build limits, including 128 principals per governed bundle and
128 distinct retrieval grant partitions, still apply. Redis and extra workers do
not increase those limits; larger deployments need a measured capacity review.
Oracle has separate NL2SQL_QUERY_POOL_MAX settings; verify its actual aggregate
limit with the DBA rather than assuming the generic SQLite pool setting controls it.

Redis failure blocks startup/readiness or returns a safe 503 on protected requests.
It never falls back to process-local counters. Quota exhaustion returns the existing
429 error contract. Liveness remains available. Redis contains only expiring quota
and active-lease state; no results, raw identity values, grants, credentials or metadata approvals are
stored there. Restart/eviction can reset quota history, so the Redis owner must
provide appropriate isolation, memory headroom and a noeviction policy. Permission
enforcement still runs independently on every request.

Redis ACLs must allow the deployment's rate/chat/probe key prefix and the script's EVAL, TIME,
ZREMRANGEBYSCORE, ZCARD, ZADD, ZSCORE, ZREM and PEXPIRE commands, plus PING and the client's approved
connection/authentication/database-selection commands. They need no CONFIG, FLUSHDB,
business-data or metadata-publication access. Keep the listener private; the browser
must never connect directly to Redis. See the official [Redis security guidance](https://redis.io/docs/latest/operate/oss_and_stack/management/security/)
and [redis-py production guidance](https://redis.io/docs/latest/develop/clients/redis-py/produsage/).

An approved private CA can be supplied with NL2SQL_REDIS_CA_BUNDLE. Certificate and
hostname checks are explicit for TLS connections; no certificate-bypass option is
supported. Corporate sign-in, TLS ingress,
proxy/UI hosting, high availability and actual VM capacity remain separate gates.

## Quick synthetic setup

From the project root, use Python 3.13 (tested baseline 3.13.16):

```powershell
python setup_env.py
.\.venv\Scripts\python -m nl2sql init-demo
.\.venv\Scripts\python -m nl2sql serve --env-file .env
```

`setup_env.py` installs the pinned core dependencies and project, creates `.env`
from its example if absent, and preserves existing settings. `init-demo` creates
fictional data and random credentials in ignored `.local/` storage. It refuses
to overwrite an existing database; skip it for an initialized demo or select a
fresh `--settings` path. Protect local credentials with OS account permissions.

The service binds to `127.0.0.1:8000`. The supplied browser UI is a frozen
reference and is not served or integrated. See [Operations](OPERATIONS.md) for
requests, metadata lifecycle, and troubleshooting.

## Manual install and validation

From this project's root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-core.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
# Optional approved Oracle driver, only when needed:
# .\.venv\Scripts\python.exe -m pip install -r requirements-oracle.lock
# Existing development tools remain pinned in requirements.lock.
.\.venv\Scripts\python.exe -m nl2sql init-demo --settings .local/hardening-demo/settings.json --catalog .local/hardening-demo/catalog.json
.\.venv\Scripts\python.exe -m nl2sql validate-config --settings .local/hardening-demo/settings.json --env-file .env.example
.\.venv\Scripts\python.exe -m nl2sql serve --settings .local/hardening-demo/settings.json --env-file .env.example
```

Initialization refuses to replace existing data. Select a fresh directory for each independent demo.
Credentials are randomly generated into its ignored directory. Never copy those credentials into
examples, reports or source control. The sanitized office template is config/office.example.json;
it deliberately cannot start an office service without approved resources and trust anchors.

## Optional Strix security assessment

Strix is separate security tooling, not an application dependency. Its nine upstream agent skills
are installed under the local Codex skills directory. The isolated CLI is pinned to `strix-agent==1.7.0`
under `~/.codex/tools/strix-1.7.0`; another installation can be selected with `--strix PATH`.
Follow the [Strix provider setup](https://docs.strix.ai/llm-providers/overview.md) for an authorized
model connection. Hosted inference sends source context to that provider. Keep credentials in
the local Strix configuration or process environment, never in this repository.

```powershell
# Inspect the sanitized snapshot without starting a scan:
.\.venv\Scripts\python.exe -m scripts.strix_scan --prepare-only
# Docker and an authorized Strix model connection must be ready:
.\.venv\Scripts\python.exe -m scripts.strix_scan --max-budget 10
# Equivalent optional hook; this does not run on ordinary commits:
.\.venv\Scripts\python.exe -m pre_commit run strix-security --hook-stage manual
```

The hook scans the full source snapshot with a USD 10 model-spend cap by default. It reuses the
exporter's exclusions for credentials, databases, private metadata and generated exports. Strix
can modify its disposable copy; the working project is not mounted into its sandbox. Synthetic
data only; company Oracle, real application providers and third-party targets are out of scope.
Snapshots, instructions and reports stay under ignored `.local/strix/`. A successful process exit
must also have one `run.json` marked `completed`; read the report and usage for partial coverage or
early budget warnings before accepting its results. Tests and lint checks are separate gates.
A provider rejection leaves the assessment incomplete; retain its logs and coverage gaps rather
than treating an empty findings list as a pass. Subscription scans consume plan allowance; the
dollar cap applies to metered model costs.

## Configuration

Precedence is process environment > explicitly selected dotenv > JSON > validated defaults.
No implicit `.env` or parent directory search occurs. The `--env-file` switch applies to application
settings; metadata commands accept the same switch and must select the same file when staging,
publishing or monitoring. Supply Oracle/query/discovery credentials and metadata trust anchors through approved
process-environment injection or the same explicitly selected private environment file.
Corporate secret managers can inject those variables without an application dependency or secret file.
Validation prints only validity and provider modes; invalid configuration never prints field values.

The root `.env.example` lists safe local defaults and the LLM, Redis, Oracle query,
Oracle discovery and optional embedding configuration references. `setup_env.py`
preserves an existing `.env`; template updates do not migrate or replace local secrets.
LLM APIs require the full chat-completions URL, exact provider model ID and JSON
array of approved hosts, plus `NL2SQL_MODEL_KEY` when bearer authentication is required.
Legacy `LLM_URL`, `LLM_KEY` and `BM_DB_*` names are not aliases for these settings.

For the VM, copy `config/vm.env.example` into a protected local file, add the approved
model settings from `.env.example`, and select that file with the office settings JSON.
Only one application dotenv is selected; files are not merged automatically. The
development template explicitly selects synthetic SQLite and must not override the
office Oracle configuration unchanged. Oracle sections in `.env.example` are commented
references: a protected copy may provide these fields through the same explicitly selected
file. Actual process environment values still win. Approval flags remain false in examples
and attest existing organizational approvals, rather than creating database permission.
The Redis Compose YAML starts only local Redis; it does not configure the separate API.

Model fields: `model_mode`, `model_name`, `model_endpoint`, `approved_model_hosts`, `model_key`,
`model_output_mode`, `model_timeout_seconds`, `model_retries`, `model_max_tokens`,
`model_context_bytes`, `model_context_tokens`, `model_token_count_endpoint`,
`model_token_safety_margin`, `model_ca_bundle`. Modes are disabled, scripted, private_http and hosted_http.
`register_model` accepts additional trusted application adapters. Authentication is optional bearer
authentication to the approved endpoint; TLS validation is always enabled. The HTTP contract is
OpenAI-compatible chat completions. Model tools, wrong IDs, malformed JSON and over-budget replies
are rejected. Output modes are JSON schema, JSON object, or explicitly configured strict text JSON
(an entire JSON document, optionally inside one JSON code fence). No raw SQL path exists.

Hosted inference additionally requires `public_model_authorized=true`, `data_classification=synthetic`,
an allowlisted HTTPS host, and a synthetic assembled catalog on every call. No hosted endpoint was
contacted in development. Private mode retains private-address and TLS checks; it does not inherit
hosted authorization. Setting an endpoint is not evidence of organizational approval.

Embedding fields: `embedding_mode` (disabled/fake/local/private_http), `embedding_model`,
`embedding_version`, `embedding_dimension`, `embedding_batch_size`, `embedding_timeout_seconds`,
`embedding_normalization`, `embedding_cache_entries`, `embedding_endpoint`,
`approved_embedding_hosts`, `embedding_key`, `embedding_local_path`, `index_storage_path`.
Fake mode is synthetic-only. For a standard saved Sentence Transformers text model, set
`embedding_mode=local` and `embedding_local_path` to its existing folder. The built-in CPU
loader infers dimension and binds identity to the saved files; it runs offline with custom
remote code disabled and safetensors required. An explicit dimension must match the model.
The same loader is available in preparation, monitoring and serving processes, including
the `office` supervisor. `register_local_embedding(model_id, factory)` remains available for
trusted custom composition with an explicit identity/version. Custom registrations are not
inherited by spawned workers. No weights or model server are downloaded automatically.
See [the Windows office installer](OFFICE_INSTALLER.md) for the complete optional dependency
lock, one-file setup, visible connection fields and remaining office qualification.

Use the same model ID/version/dimension/normalization at staging, publication and serving.
Changed embedding or retrieval configuration requires staging/reviewing a compatible candidate.
It cannot silently replace the active index. Provider calls are batched and coalesced; malformed,
late or incomplete batches do not enter the cache. HTTP calls obey bounded transport deadlines.
Installed local adapters must implement interruption in their runtime; the wrapper rejects late
results and explicit cancellation but cannot forcibly interrupt arbitrary third-party Python code.

Retrieval fields are `retrieval_top_k`, `retrieval_max_candidates`, `retrieval_rrf_constant`,
`retrieval_max_text_bytes` (10,000,000) and `retrieval_max_native_mb` (1,024 per live retriever), plus
`model_context_bytes`. Exact matching and BM25 remain mandatory. Native search uses bounded
overfetch and never repeats the Python cosine scan. Rich records contain certified semantic
evidence, not unapproved physical inventory. Scope filtering removes hidden records and links.
The compiler independently validates the final plan and graph regardless of retrieval rank.

Metadata configuration uses `metadata_root`, its protected source profile, signed publication
pointer and candidate store. Existing hard build budgets remain enforced. Scheduling is disabled
by default and enabled only through the authenticated administrative schedule command outside
API workers. Ordinary restart verifies the saved approved snapshot without discovery. Set
`metadata_startup_reconcile=true` when the approved deployment requires a physical startup gate.
Office owners must specify freshness and continuous drift-monitor requirements before transfer.
Known quarantined mappings and revoked grants remain blocked under either startup policy.

Optional vector snapshots require a directory within storage marked `.metadata-private`.
They contain content hashes and vectors, not original schema text or customer rows. Checksums
detect corruption; signed bundle fingerprints enforce compatibility. Invalid snapshots rebuild.
Memory caches are bounded; operators must apply an approved retention policy to old disk snapshots
and metadata history. Existing pinned runtime resources drain before closure.

## Operations and evidence

`/health` and existing EWS endpoints retain their response shapes. The authenticated
`/api/v1/health/components` route distinguishes published/pinned metadata, database readiness,
index compatibility and disabled/configured inference. `configured_unprobed` does not claim
external-service availability. It performs no inference request. Logs include durations and safe
status codes, without prompts, SQL binds, credentials or confidential schema text.

```powershell
.\.venv\Scripts\python.exe scripts/check.py
.\.venv\Scripts\python.exe scripts/benchmark.py
.\.venv\Scripts\python.exe scripts/retrieval_benchmark.py
.\.venv\Scripts\python.exe scripts/schema_evolution.py
.\.venv\Scripts\python.exe scripts/concurrency_benchmark.py
.\.venv\Scripts\python.exe export_project_to_txt.py
```

Git must be on PATH for the existing pre-commit gate. Benchmark outputs distinguish scripted
workflow correctness, retrieval-only ablations and application-service load. Load measurements
include actual pool and session queue timings under Python tracing; they are not HTTP SLO proof.
`compare_models` accepts explicit authorized provider factories for the same synthetic workflow
suite. Its invalid-output fixtures are scripted contract cases; an independently held-out business
corpus remains necessary for model selection and enterprise release.

## Office handoff — do not execute here

Obtain steward-owned definitions, units/scales, owners, composite keys, grains, calendars and
logical-join review references. Logical evidence is a proposal; signed physical/business/security
reviews still authorize publication. Discovery cannot certify a join or grant access.
Provision restricted storage and process-environment secrets through company-approved tooling.
Have the DBA establish read-only query grants, VPD/context set/reset and resource limits separately
from discovery permissions. Qualify real NUMBER/TIMESTAMP behavior, driver cancellation and pool
cleanup using an approved synthetic Oracle environment. Configure corporate identity and revocation.
Qualify the existing embedding runtime and actual inference with held-out accuracy and load tests.
Choose freshness/startup gates and scheduler/alert/retention ownership. Review final test and
performance evidence before release. No deployment, public publication or remote push is authorized.


## Embedded graph configuration

For the verified portable Windows Python/SQLite candidate and early setup checks, see
[Windows runtime qualification](WINDOWS_RUNTIME.md). Company approval remains separate.

SurrealDB Python `2.0.0` includes the embedded engine and requires no graph endpoint,
API key, separate server or application OpenSSL directory hook. Install pinned requirements
into a fresh platform-specific virtual environment. No model weights are installed.

`data_dir/graphs/<catalog-digest>.surreal.json` is an immutable rebuild snapshot;
each worker/retained bundle owns an in-memory SurrealDB projection. Shared SurrealKV is
intentionally not used because it locks a persistent directory to one process.
Remove old `graph_buffer_mb`/`graph_native_dir` JSON fields and
`NL2SQL_GRAPH_BUFFER_MB`/`NL2SQL_GRAPH_NATIVE_DIR` environment entries. The JSON loader
rejects obsolete fields rather than silently pretending to apply native limits.
`retrieval_max_native_mb` is retained for configuration compatibility as a conservative
32 MiB-per-nonempty-vector-partition admission estimate, not a hard memory cap. Component,
dimension, record and text limits also apply. Measure total RSS with actual worker counts.
See [migration instructions](SURREALDB_MIGRATION.md), OPERATIONS.md and ARCHITECTURE.md.



## Planning decisions, storage upgrades and office admission

HTTP inference requests the object-shaped `PlanningDecision` schema:
`{"outcome": <QueryPlan>}` or
`{"outcome":{"kind":"clarification","reason":"period","metric_ids":[]}}`.
Reasons are metric/period/dimension/filter/entity. The application verifies suggested metric IDs
against authorized retrieved candidates and supplies the question wording; a clarification executes
no SQL. Existing direct QueryPlan responses remain readable by the adapter. Default `json_schema`
mode carries the schema in response_format rather than repeating it in metadata. Other output
modes include the schema in the bounded context. Runtime token counting and output reserve remain
mandatory for restricted HTTP inference.

An owned last plan and one pending bounded question may enter model context only under the current
catalog and scope identity. Changed grants clear model-visible context; supported deterministic
follow-ups still revalidate against the current scope. Unusable old context is discarded rather
than blocking a new complete question. Prior result rows and transcripts are never planning authority.

Local repositories use SQLite user_version 3. Version 0 tables are adopted, format tags added in
version 2, and pending-question/scope columns added in version 3. Legacy metadata format 1 retains
its signed identity; new format 2 preserves field presence while explicitly retaining timestamps.
Unknown future database/record formats fail closed. Back up before upgrading; downgrade by restoring
a coherent previous-release backup, not by deleting columns or lowering user_version.

The 20-user target is a workload size, not a model concurrency setting. The office example starts
with eight overall chats and one inference; global overload returns CHAT_CAPACITY/429 and Retry-After, without an unbounded
waiting queue. The two chat endpoints share admission and success/failure pipeline metrics.
Application deadlines begin before authentication, bound reload-lock waits, and cannot be extended
by nested chat calls. Late resource candidates are closed rather than activated. A native provider
must still implement its own interruption; these controls do not forcibly kill arbitrary Python code.

FTS preflight counts metric and schema document text across unique grant partitions. Vector
partition memory estimates are checked before encoding/allocation; vector components are bounded
before native index allocation. These are admission/input budgets, not native allocator or process
RSS caps. Workers and overlapping bundles multiply costs; measure the actual SLM and target machine
before raising limits.

RuntimeFactory captures Oracle query configuration once during composition. Discovery and query
accounts remain separate. Office preflight rejects known unpatched SQLite, relative/repository
storage paths and recognizable synchronized folders. It cannot certify filesystem ACLs, encryption
or an arbitrary mounted filesystem; the company must approve the actual local volume.

Official SQLite advisory: https://sqlite.org/wal.html#walresetbug.

The office examples target `model_context_tokens=100000` in both JSON and environment
configuration. The generic application/development default remains 8192 for other runtimes.
Actual process environment overrides the selected environment file, which overrides JSON;
clear stale values when qualifying the office profile. This configuration does not allocate
model memory or establish native model support. Verify effective context per request/slot,
the same-origin runtime token counter and output reserve on the selected inference runtime.
`model_context_bytes` remains a separate 64000-byte metadata bound by default; a 100K token
ceiling is not a requirement to fill it. Existing 60-second model and 120-second office-turn
budgets still apply; use measured prefill/generation behavior before changing timeout policy.
