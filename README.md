# EWS NL2SQL backend

Synthetic-first Python 3.13/FastAPI backend for governed natural-language queries,
typed query plans, validated SQL, and read-only execution. Existing EWS UI assets
are preserved for a separately authorized integration; no replacement UI is built.

## Documentation

- [Setup and configuration](docs/CONFIGURATION.md): pinned environment, synthetic
  startup, provider settings, checks, and office qualification.
- [Operations](docs/OPERATIONS.md): requests, metadata bootstrap/review/publication,
  refresh, rollback, and troubleshooting.
- [Current architecture](docs/ARCHITECTURE.md): implementation, supported SQL,
  authorization, exact money, and release limits.
- [Architecture diagram](docs/ARCHITECTURE_DIAGRAM.md): Azure-style overview with
  SVG, PNG and editable draw.io formats, plus source traceability.
- [Code structure](docs/STRUCTURE.md): package ownership, import boundaries and tests.
- [Design reference](docs/DESIGN_REFERENCE.md): the original numbered proposal
  consolidated into one document.
- [Redis and code-quality review](reports/redis-and-code-quality-review-2026-10-21.md):
  completed fixes, local verification and remaining office release requirements.

Quick local start from this directory:

```powershell
python setup_env.py
.\.venv\Scripts\python -m nl2sql init-demo
.\.venv\Scripts\python -m nl2sql serve --env-file .env
```

Run `init-demo` only for a fresh demo; it refuses to replace existing data.
Existing settings and credentials stay in ignored local storage. Never commit
`.env`, credentials, inventories, approvals, snapshots, or company data.

Company Oracle, corporate identity, real models/embeddings, and production
deployment still require qualification and approval. Local tests use synthetic
data and controlled fakes.

Use `.\.venv\Scripts\python scripts/check.py` for the mandatory quality gates.
The source exporter is `python export_project_to_txt.py`; its generated output
is ignored and excludes private runtime data.

For concurrent VM workers, the shared Redis limiter is implemented. Install
`requirements-redis.lock`, inject the approved Redis URL, and select
`config/vm.env.example` with the chosen settings file. The supported launcher is
`python -m nl2sql serve --settings <settings.json> --env-file config/vm.env.example`.
See the configuration and operations guides before office use; no VM deployment
or real-provider qualification is implied by this setup.

To exercise real local Redis with random credentials and isolated test/application
ACLs, run `python scripts/redis_local.py`, then
`docker compose -f config/redis.local.compose.yaml up -d`. Verify the connection with
`python -m nl2sql check-redis --env-file .local/redis/local.env` and run all checks
with `python scripts/check.py --redis-env .local/redis/test.env`.
See [Operations](docs/OPERATIONS.md#redis-verification) for synthetic startup,
shared rate/active-chat limits, failure recovery and session-retention maintenance.
