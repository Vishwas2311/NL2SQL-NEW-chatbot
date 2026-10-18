# Setup and configuration

This is a synthetic Windows/Python 3.13 development build. Company Oracle, corporate identity,
real inference, installed embedding runtimes and native FAISS require separate qualification.
Original numbered designs are consolidated in [Design reference](DESIGN_REFERENCE.md). UI assets are preserved.

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
