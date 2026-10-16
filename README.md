# EWS V4.3 metadata-driven NL-to-SQL backend

Latest local verification: **328 tests, 89% coverage and all quality gates passed**, including the one-command setup follow-up.
See the [configuration/handoff runbook](DEVELOPMENT_HARDENING_RUNBOOK.md).
Company Oracle, corporate identity, real inference and embeddings still need office qualification.

The V4.3 upgrade adds dictionary discovery, signed metadata approval, atomic runtime bundles,
drift impacts and optional external refresh. Start with [tested operations](ORACLE_BOOTSTRAP_RUNBOOK.md).
Existing synthetic startup below remains supported.

Working synthetic-first FastAPI backend. The supplied HTML/CSS/JS remains untouched and is not
served or integrated. This implementation is a local development baseline, not an enterprise release.

Python baseline: **3.13.16**. Create the environment and `.env` with one command:

```powershell
python setup_env.py
```

This creates `.venv`, installs the pinned core dependencies and the project, and copies
the clearly labelled `.env.example` to `.env`. Existing `.env` settings are preserved.
The Oracle driver and development tools remain optional; install `requirements-oracle.lock`
or `requirements.lock` into `.venv` when needed. `.env` stays excluded from Git.

Then initialize a fresh synthetic demo and start it from this directory in PowerShell:

```powershell
.\.venv\Scripts\python -m nl2sql init-demo
.\.venv\Scripts\python -m nl2sql serve --env-file .env
```

Run `init-demo` once for a fresh checkout. If a demo is already initialized, skip that step or select
a new `--settings` path; initialization refuses to overwrite an existing database. It creates fictional data, an approved synthetic catalog,
and random credentials in ignored `.local/` files. No shared default bearer token exists. Protect
that directory with your OS account permissions. The service binds to `127.0.0.1:8000`.

```powershell
$demoCredentials = Get-Content .local/demo-credentials.json -Raw | ConvertFrom-Json
$demoHeaders = @{ Authorization = "Bearer $($demoCredentials.analyst)" }
$demoBody = @{ message = 'Show total loan exposure by region'; user_id = 'analyst' } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ews-chatbot/chat -Method Post -Headers $demoHeaders -ContentType application/json -Body $demoBody
```

Actual expected rows:

```json
[
  {"region":"Demo North","loan_exposure":"175000.50"},
  {"region":"Demo South","loan_exposure":"75000.00"}
]
```

Money is serialized as exact decimal strings in INR. This report is for **2026-09-30**; source refresh
time is explicitly unknown. Closed loans and another tenant's overlapping customer IDs are excluded.
The narrower `north_analyst` credential can retrieve only Demo North.

Additional certified questions (zero model calls):

- `Show total loan exposure`
- `Show loan count by region`
- `Show account count by region`
- `Show average exposure by region`

Continue a dated loan conversation with `What about 2025?`, supplying the returned `session_id`.
The existing UI's browser token placeholders are not recognized. Browser `user_id` cannot set identity.

| Route | Behavior |
|---|---|
| GET `/health` | Public compatible liveness |
| GET `/api/v1/health/ready` | Synthetic DB readiness |
| POST `/ews-chatbot/chat` | Authenticated legacy request/response |
| GET `/ews-chatbot/get_all_sessions` | At most 100 owned conversations |
| GET `/ews-chatbot/load_session/{id}` | Owned history; old content redacted on grant change |
| DELETE `/ews-chatbot/delete_session/{id}` | Owned deletion |
| POST `/api/v1/chat` | Typed internal answer envelope |
| GET/DELETE `/api/v1/sessions/{id}` | Internal session aliases |
| GET `/api/v1/sessions` | Internal listing alias |
| POST `/api/v1/speech/transcriptions` | Authenticated, explicitly disabled (501) |

Requests and responses are synchronous JSON. SQL/schema/binds are never included in chat responses.
Speech, export, result pagination and cancellation jobs have no implemented product surface.

The compiler supports certified SUM/COUNT/MIN/MAX, exact displayed averages, composite-key joins,
nested typed AND/OR filters, bounded IN, null tests, multiple grouping fields, HAVING and ordering.
The v2 synthetic catalog adds half-open event date ranges, certified April fiscal years, snapshot
ranges grouped by reporting date, net amounts and exact percentage formatting, aggregate CTEs,
ROW_NUMBER/DENSE_RANK after aggregation, and certified customer-grain multi-fact preaggregation.
Average/ratio sorting or HAVING, arbitrary formulas/joins/windows/CTEs, currency conversion, historical
current-only attributes and period-over-period comparisons remain explicitly unsupported.
Raw-SQL fallback has **no enabled route or execution API**.

For flexible wording, configure a specifically approved private OpenAI-compatible inference endpoint
in the selected settings JSON: `model_mode=private_http`, `model_endpoint` (complete chat-completions URL),
`approved_model_hosts`, and the exact `model_name`. Non-loopback HTTP and public IPs are rejected;
TLS verification and no redirects/proxy inheritance are defaults. The configured name is
`gemma-4-12b`; availability/checkpoint compatibility has not been verified. No weights/runtime were
downloaded. Provider tests use MockModel and HTTPX MockTransport, not real Gemma.

Authentication supports random opaque local tokens and validated HS256 JWTs with required issuer,
audience, expiry and subject, then resolves current server-side grants. Corporate SSO, asymmetric
key rotation and entitlement synchronization need a separately approved identity adapter.

```powershell
.\.venv\Scripts\python scripts/check.py
.\.venv\Scripts\python scripts/benchmark.py
.\.venv\Scripts\python scripts/retrieval_benchmark.py
```

The first command runs Ruff lint/format, Pylint, strict Pyright, Pytest/coverage and pre-commit.
No hook is installed into `.git/hooks` automatically. The GitHub Actions workflow runs the same
checks if you later authorize publishing to an approved repository; it has not run remotely.

Source layout:

- `backend/nl2sql/domain.py`: immutable contracts and safe errors.
- `catalog.py`, `retrieval.py`, `planning.py`: approved metadata, NetworkX, FTS5, semantic proof.
- `compiler.py`, `security.py`, `database.py`: SQL AST, independent checks, signed capability, RO pool.
- `model.py`, `oracle.py`: private inference and gated Oracle adapters.
- `service.py`, `sessions.py`, `auth.py`, `api.py`: application pipeline, persistence, identity, transport.
- `metadata/synthetic/`: fictional catalog; `tests/`: unit/security/contract/E2E fixtures.
- `scripts/`, `reports/`, `docs/`: checks, measured evidence and operating instructions.

See the retained operating guides for supported configuration and office qualification, and `reports/` for measured local evidence.

To combine the available project source, tests, configuration, documentation and UI reference files
into one text file, run `python export_project_to_txt.py` from this folder. It creates
`full_project_export.txt` beside the script. Local runtime data/credentials, environment files,
dependencies, caches, binaries and previous exports are excluded; project files remain unchanged.

The separate v2 demo is initialized at `.local/audit-v2/`; use it without changing v1 data:

```powershell
.\.venv\Scripts\python -m nl2sql serve --settings .local/audit-v2/settings.json
```

For a fresh v2 demo in another directory, run:

```powershell
.\.venv\Scripts\python -m nl2sql init-demo --settings .local/my-v2/settings.json --catalog metadata/synthetic/catalog-v2.json
```

Flexible new operations require typed plans from the approved private model; the five exact templates
remain available with inference disabled. Tests and evaluation inject scripted plans explicitly.
`reports/benchmark.json` now contains 46 distinct local goldens, not two repeated questions.
Hybrid comparison accepts an injected approved `EmbeddingProvider` through
`nl2sql.retrieval_experiment.compare_retrieval`; its default report marks hybrid as not run.
No encoder weights, FAISS or vector service are installed.
