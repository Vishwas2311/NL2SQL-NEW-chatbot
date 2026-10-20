# Setup and configuration

This is a synthetic Windows/Python 3.13 development build. Company Oracle, corporate identity,
real inference, installed embedding runtimes and native FAISS require separate qualification.
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
| max_concurrent_chats_per_principal | 1 active chat per authenticated tenant/subject |
| admission_lease_seconds | 300; must exceed request_timeout_seconds plus twice redis_timeout_seconds plus 5 seconds |
| api_workers | 1 for development; VM template 2; allowed 1..16 |
| http_concurrency_limit | 64 accepted connections/tasks per worker; tune with HTTP load |
| max_session_bytes | 4,000,000 UTF-8 bytes of serialized messages per conversation |

Each setting maps to its upper-case NL2SQL_ environment name. Shared limits apply
only to workers using the same Redis service/database and deployment prefix. Grant
changes do not reset a subject's rate counter or active slot. Both chat routes hold
slots through planning, execution and persistence; session routes use rate quotas
without taking chat slots. Active-limit rejections still count toward the rate quota.
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
total configured query connections are approximately workers times pool size.
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
process-environment injection; their existing separate settings classes never search dotenv files.
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
**process-environment references**: keep them commented in application dotenv files.
Their separate settings loaders do not read `--env-file`; uncommenting their account
variables there causes unknown-setting validation errors. Inject them into the process
through the approved launcher/secret manager instead. Approval flags remain false in
examples and attest existing organizational approvals, rather than creating permission.
The Redis Compose YAML starts only local Redis; it does not configure the separate API.

Model fields: `model_mode`, `model_name`, `model_endpoint`, `approved_model_hosts`, `model_key`,
`model_output_mode`, `model_timeout_seconds`, `model_retries`, `model_max_tokens`,
`model_context_bytes`, `model_ca_bundle`. Modes are disabled, scripted, private_http and hosted_http.
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
Fake mode is synthetic-only. An installed local runtime must be explicitly registered with
`register_local_embedding(model_id, factory)`; the factory receives an existing model path and must
implement the typed encode port. There is no implicit import, server installation or model download.
Office runtime integration is unqualified until its real adapter is supplied and tested.

Use the same model ID/version/dimension/normalization at staging, publication and serving.
Changed embedding or retrieval configuration requires staging/reviewing a compatible candidate.
It cannot silently replace the active index. Provider calls are batched and coalesced; malformed,
late or incomplete batches do not enter the cache. HTTP calls obey bounded transport deadlines.
Installed local adapters must implement interruption in their runtime; the wrapper rejects late
results and explicit cancellation but cannot forcibly interrupt arbitrary third-party Python code.

Retrieval fields are `retrieval_top_k`, `retrieval_max_candidates`, `retrieval_rrf_constant` and
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
