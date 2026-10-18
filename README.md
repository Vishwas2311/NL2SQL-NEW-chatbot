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
- [Design reference](docs/DESIGN_REFERENCE.md): the original numbered proposal
  consolidated into one document.

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
