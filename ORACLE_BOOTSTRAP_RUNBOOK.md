# V4.3 operations (PowerShell)

Run from the project directory. Local synthetic commands below are exercised by CLI/API tests.
Corporate commands are implemented, parser/authorization/dictionary-contract tested, but **not run
against Oracle**. They require organizational approval, credentials and reviewed mappings first.
No command in this document authorizes a company connection or model download.

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
