# Operations

Run from the project directory. Local synthetic commands below are exercised by CLI/API tests.
Corporate commands are implemented, parser/authorization/dictionary-contract tested, but **not run
against Oracle**. They require organizational approval, credentials and reviewed mappings first.
No command in this document authorizes a company connection or model download.

The concurrent VM profile uses the existing approved Redis service for shared
rolling-minute request quotas, global/per-principal active-chat leases and an
importable API worker factory. Single-process
synthetic development retains its memory limiter. Retained UI assets live only
under `UI/*/existing_ui_reference/`, with their original hash manifest and unchanged
JavaScript contract test. No UI integration or office service deployment is performed.

Keep restricted runtime databases, credentials, metadata and backups outside
cloud-synchronized source folders and on an approved local volume. A private
marker or Git ignore rule does not enforce Windows access permissions or disable
cloud sync. Verify these properties on the office machine before restricted use.

## Concurrent workers and Redis

Follow CONFIGURATION.md to install requirements-redis.lock and provision the Redis
URL through approved secret injection. The examples below describe prepared
commands, not approval to connect to office Oracle or deploy the application.

With an initialized synthetic settings file and an approved local test Redis:

```text
python -m nl2sql serve --settings .local/settings.json --env-file config/vm.env.example
```

The VM template defaults to two workers. `--workers N` can override it after memory,
model and database capacity review. Keep the development .env file out of the VM
command: it explicitly selects a single-process memory limiter and environment
values override JSON settings. Both files are opt-in; nothing is implicitly loaded.

Use an approved same-VM reverse proxy for user-facing HTTPS, corporate sign-in and
routing to the loopback API. Do not expose the Redis port to users or change the
immutable UI assets as part of this backend change. Actual ingress/deployment setup
depends on the VM OS and corporate platform and has not been installed here.

Probe `/health` for process liveness and `/api/v1/health/ready` for database plus
Redis readiness. The authenticated components route also reports the selected
rate_limiter backend. If Redis is unavailable, protected requests receive
RATE_LIMIT_UNAVAILABLE/503 and no process-local fallback occurs; quota exhaustion
receives RATE_LIMIT/429. Inspect sanitized status codes, Redis availability/ACLs,
connection limits and TLS trust without printing the Redis URL or credentials.
Restart the API after credential/configuration rotation; no live client-rotation
mechanism is claimed. Redis restart resets transient quotas, not durable grants.

Each API worker owns its pools/indexes/clients. Keep all workers pointed at the
same local session/metadata repositories and Redis deployment prefix. Monitor
aggregate Oracle connections, worker RAM, Redis latency/memory and session queue
time. Shared Redis quotas do not remove SQLite write contention; qualify sustained
HTTP load before increasing worker/user counts. Multi-node SQLite/HA is not qualified.

## Redis verification

### Reproducible local synthetic connection

Docker Desktop is optional and used only for this local verification. Install the
pinned Redis client first. From a fresh checkout, prepare random local credentials
and separate least-privilege application/test ACLs, then start the isolated service:

```text
python scripts/redis_local.py
docker compose -f config/redis.local.compose.yaml up -d
python -m nl2sql check-redis --env-file .local/redis/local.env
```

The service binds only 127.0.0.1:6380, uses Redis 8.2.10-alpine, disables the default
user, and limits memory with noeviction. It stores transient admission state only;
disk snapshots/AOF are disabled for this synthetic service. The application account
cannot read test keys or run CONFIG/FLUSHDB. The test account has its own key prefix
and limited inspection/cleanup commands. Credentials are never command arguments.
Generated files remain under ignored .local/redis/. Preparation copies local.env
to .env only when .env is absent; existing settings and passwords are never replaced.
Keep all these synthetic files out of office secret provisioning and source control.

check-redis validates Redis authentication and scripting/sorted-set permissions,
without starting application database or model resources. Output omits the URL and
credentials. It uses selected settings/dotenv/process-environment precedence.

For the existing initialized synthetic demo, serve with:

```text
python -m nl2sql serve --settings .local/settings.json --env-file .local/redis/local.env
```

For a fresh demo initialize once before serving; initialization refuses replacement:

```text
python -m nl2sql init-demo --settings .local/redis-demo/settings.json --catalog .local/redis-demo/catalog.json
python -m nl2sql serve --settings .local/redis-demo/settings.json --env-file .local/redis/local.env
```

Run every mandatory check with the explicit isolated test identity, including the
real Lua and two-spawned-worker HTTP tests:

```text
python scripts/check.py --redis-env .local/redis/test.env
```

Stop only this local service with `docker compose -f config/redis.local.compose.yaml stop`.
Starting it again reloads ACLs and resets transient quotas/leases. Saved SQLite
conversations survive. Drain API work before planned Redis restart; leases are not
provider-side cancellation or physical fencing after Redis loses state.

### Existing approved Redis service

The mandatory local suite exercises adapter contracts, outages, concurrency and
worker configuration without needing a server. Actual Lua execution requires an
explicit isolated local Redis. Set NL2SQL_TEST_REDIS_URL to that approved local test
store and run:

```text
python -m pytest -q tests/integration/test_redis.py tests/integration/test_redis_workers.py --no-cov
```

The fixture accepts loopback hosts only, creates unique synthetic key namespaces
and deletes only its own keys. It never runs FLUSHDB. If the test URL is absent the
real-server tests explicitly skip; if it is selected but unavailable they fail.
The spawned-worker test launches the supported CLI with two workers, requires both
worker PIDs to serve HTTP, and verifies shared quotas, exact synthetic query results
and durable session history. It tears down only its own supervisor/worker tree.
The prepared Linux CI job supplies Redis 8.2.10 and runs this suite. No CI execution
or VM Redis qualification is implied merely by adding the workflow.

## Environment and checks

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.lock
.\.venv\Scripts\python -m pip install --no-deps -e .
.\.venv\Scripts\python scripts/check.py
.\.venv\Scripts\python scripts/benchmark.py
.\.venv\Scripts\python scripts/retrieval_benchmark.py
.\.venv\Scripts\python scripts/schema_evolution.py
```

Python 3.13 is required; tested interpreter 3.13.16. Pinned dependencies were already installed and
checked in this workspace. Git must be on PATH for pre-commit. This Codex environment used
`C:\Users\vishw\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd` on the
current process PATH. No machine-wide environment change is required.

## First synthetic bootstrap and explicit fictional approvals

Use a fresh directory; init-demo refuses to overwrite existing business data. Bootstrap alone never
activates metadata. Dry-run of a new store leaves the requested target directory untouched.

```powershell
$metaRoot = '.local/metadata-v43-demo'
.\.venv\Scripts\python -m nl2sql metadata bootstrap --source synthetic --root $metaRoot --dry-run
$candidate = (.\.venv\Scripts\python -m nl2sql metadata bootstrap --source synthetic --root $metaRoot | ConvertFrom-Json).candidate_id
.\.venv\Scripts\python -m nl2sql metadata status --root $metaRoot
.\.venv\Scripts\python -m nl2sql metadata demo-trust --root $metaRoot
$demoTrust = Get-Content "$metaRoot/demo-credentials.json" -Raw | ConvertFrom-Json
$demoTrust.PSObject.Properties | ForEach-Object { [Environment]::SetEnvironmentVariable($_.Name, [string]$_.Value, 'Process') }
.\.venv\Scripts\python -m nl2sql metadata inspect --root $metaRoot --candidate-id $candidate
$signed = .\.venv\Scripts\python -m nl2sql metadata sign-demo --root $metaRoot --candidate-id $candidate | ConvertFrom-Json
.\.venv\Scripts\python -m nl2sql metadata approve --root $metaRoot --candidate-id $candidate --approval-file $signed.private_output
.\.venv\Scripts\python -m nl2sql metadata publish --root $metaRoot --candidate-id $candidate
.\.venv\Scripts\python -m nl2sql serve --settings "$metaRoot/data/settings.json" --metadata-root $metaRoot --port 8000
```

The final command runs in the foreground; use another PowerShell terminal for requests/status.
Copy the process trust variables there through the same private-file loading block if needed.
Demo admin credentials expire in one hour. Do not use demo trust for corporate metadata; both
source/classification checks and signature evidence reject that use. Do not print or export the file.

```powershell
$demoCredentials = Get-Content "$metaRoot/data/demo-credentials.json" -Raw | ConvertFrom-Json
$demoHeaders = @{ Authorization = "Bearer $($demoCredentials.analyst)" }
$demoBody = @{ message = 'Show total loan exposure by region' } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ews-chatbot/chat -Method Post -Headers $demoHeaders -ContentType application/json -Body $demoBody
```

Expected: Demo North 175000.50; Demo South 75000.00. Existing EWS request/response keys, ownership
and authentication remain unchanged. UI files are neither served nor modified.

## Status, synchronization, scheduling and safe rollback

```powershell
.\.venv\Scripts\python -m nl2sql metadata status --root $metaRoot
.\.venv\Scripts\python -m nl2sql metadata sync --root $metaRoot --dry-run
.\.venv\Scripts\python -m nl2sql metadata sync --root $metaRoot
.\.venv\Scripts\python -m nl2sql metadata schedule --root $metaRoot --enable --interval 900 --dry-run
.\.venv\Scripts\python -m nl2sql metadata monitor --root $metaRoot --once
.\.venv\Scripts\python -m nl2sql metadata schedule --root $metaRoot --disable
.\.venv\Scripts\python -m nl2sql metadata rollback --root $metaRoot --version $candidate
```

For a deliberately approved foreground poller, run `metadata monitor --root $metaRoot` after enabling
the schedule; Ctrl+C stops it. No OS job/service is installed. Omit schedule --dry-run only when staging
is intended. Polling never approves/publishes automatically. To retire/reject an inactive version:
`metadata retire --root $metaRoot --version <id>` or `metadata reject --root $metaRoot --version <id>`.
The active version cannot be retired. Rollback rejects incompatible sources, revoked trust or old grants.

## Authorized Oracle bootstrap (live qualification blocked)

The commented Oracle sections of `.env.example` enumerate the query and discovery
process-environment variables, including credentials, approval flags and DBA context
routines. Keep them commented in an application dotenv: `--env-file` does not load
Oracle account settings. Provision them through the approved process launcher or
secret manager. A template change does not authorize or establish live connectivity.

Ask the DBA/security owners for dictionary visibility on explicit owners, network approval and a
read-only discovery identity. Obtain business/security certification separately. Source profile,
inventory, snapshots, approval files and indexes belong in company-approved restricted storage.

The implemented environment contract is `NL2SQL_DISCOVERY_` plus SOURCE_ID, OWNERS (JSON array),
DSN, USER, PASSWORD, APPROVED_ENVIRONMENT, OWNER_AUTHORIZED, NETWORK_AUTHORIZED and optional
TIMEOUT_SECONDS/MAX_ROWS/MAX_BYTES. Secret values must be injected by an approved secret manager.
All three authorization flags default false. Only set them after the actual approvals exist.

The following command's guard and dictionary adapter were tested with fictional fixtures. It is
**not live-qualified** and was not used to contact Oracle:

```powershell
.\.venv\Scripts\python -m nl2sql metadata bootstrap --source oracle --root C:\Restricted\nl2sql-metadata --dry-run
```

After authorization, remove --dry-run to persist a candidate. Without semantic/security mappings it
stays pending_verification. Do not mark a physical object approved to bypass this state. Supply a
reviewed catalog through --semantic-file and protected principal grants through --grants-file on sync.
For query readiness also supply --settings pointing to a validated Settings JSON with query_backend
oracle, metadata_root, authentication, sessions and budgets. Oracle mappings must declare exact
physical_owner/physical_name/column names, policy and units; omit default synthetic entities by
explicitly setting entities=[] when inappropriate.

Query credentials use separate `NL2SQL_QUERY_` DSN/USER/PASSWORD plus APPROVED_ENVIRONMENT,
OWNER_AUTHORIZED, NETWORK_AUTHORIZED, READONLY_GRANTS_VERIFIED and CONTEXT_PROCEDURES_VERIFIED.
APPLY_PROCEDURE and RESET_PROCEDURE must name DBA-approved schema.package.procedure routines.
No procedure or database privilege is created by this application. Corporate execution/VPD/grants/
plans/cancellation/cleanup remain DBA qualification gates.

Review with inspect; obtain a private JSON approval file `{ "approvals": ["signed-token", ...] }`
from configured physical/business/security reviewers. Trust references use
NL2SQL_METADATA_REVIEWERS entries with id, roles and key_env; the keys/admin token come from
protected environment variables. Use approve/publish as above. Publication performs live rediscovery
and runtime readiness and cannot succeed from an offline Oracle inventory alone.

For a later column, sync --dry-run, persist sync, inspect impacts, revise only approved mappings/grants,
collect fresh signatures, approve and publish. Unknown business/operator semantics remain blocked.
No real Oracle/Gemma/FAISS installation, server deployment or company approval is claimed.


## Local troubleshooting and shutdown


Start with `python -m nl2sql serve` inside the pinned environment, or the explicit `.venv` interpreter
commands in [Setup and configuration](CONFIGURATION.md). Local settings are read from `.local/settings.json`; no environment credentials
are emitted in startup messages. Defaults bind loopback. Check `/health` and `/api/v1/health/ready`.

If startup fails: verify the local catalog path and pinned digest, read-only business DB availability,
session directory permissions and authentication configuration. Startup rejects missing credentials or
an unapproved catalog. Never repair digest failures by blindly recomputing an approval pin over unknown
metadata. Reconcile and approve the source first, then rebuild derived resources/restart.

If flexible questions return MODEL_UNAVAILABLE: certified exact reports can still work. Configure an
approved private inference host and exact runtime model name only after approval. No automatic weights
or fallback are enabled. Runtime readiness currently checks local dependencies, not model readiness.

If database queries time out: narrow scope, check configured limits and inspect correlation IDs in
structured logs. Do not automatically replay a timed-out query. Logs omit prompts, SQL, binds, customer
rows, bearer tokens and DSNs. Pipeline spans record compile/validation/database/model/retrieval timings.

If a metric result is wrong: stop serving the affected catalog version, retain protected audit evidence,
compare the independent golden fixtures and roll back the approved artifact as a whole. Do not patch
business definitions through a model prompt. The local service requires restart for catalog/grant updates.

For access revocation: remove the local grant/token and restart. Public history redacts when current
principal grants differ from saved scope. Session responses recheck identity after
reads; public titles are generic so a grant change cannot expose old question text
through sidebar summaries. Governed publication refreshes current grants; corporate
sign-in/token revocation still needs approved enterprise identity integration.

Expired conversations are inaccessible but remain owner-deletable. Run bounded
retention maintenance outside API workers after approving the retention policy:

```text
python -m nl2sql purge-sessions --settings <protected-settings.json> --limit 1000
```

The command deletes at most the selected batch of expired sessions and cascaded
messages. Repeat under approved maintenance scheduling if more remain; no API
worker scheduler is installed. This does not purge backups or establish secure
physical erasure from WAL files/storage. History reads/appends also enforce the
configured UTF-8 byte budget and existing 200-message ceiling.

Shutdown with Ctrl+C. Lifespan closes model HTTP clients, FTS indexes, business connections and sessions.
Back up `.local/sessions.db` through an approved SQLite-consistent procedure; protect local bearer files.
Do not copy `.local/` to source control. Development initialization refuses to overwrite existing data.

Oracle integration: use the gated adapter only in an approved synthetic Oracle test schema. Implement
DBA-owned OracleContextPolicy, prove pooled reset and DB-enforced scope, validate DATE/NUMBER/null/dialect
behavior, and repeat the injected-pool resource/cancellation/byte-budget cases against the real driver/server. No DDL is emitted by the chatbot.
EXPLAIN PLAN is not implemented and no cost-security guarantee is claimed.

Before enterprise release: complete the qualification gates in [Architecture](ARCHITECTURE.md#release-qualification), security/dependency/license review, actual CI,
real model/Oracle goldens, monitoring, rollback and source/data residency approvals. No deployment is
automatically triggered by the prepared workflow.
