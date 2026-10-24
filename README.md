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

Dependency files use the conventional pip layout: `pyproject.toml` declares project/build
metadata and `requirements.txt` pins the complete tested install set. Setup and CI use
`requirements.txt`; it includes Oracle/Redis clients, quality tools and the Windows x64
CPU embedding runtime. Model weights and external servers are supplied separately.

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
`requirements.txt`, inject the approved Redis URL, and select
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

For a complete Windows office environment, use [install_office.py](docs/OFFICE_INSTALLER.md).
It installs the pinned core, Oracle/Redis clients, local CPU embedding runtime and quality
tools, creates visible private connection fields and checks readiness before startup.
`python3.13 setup_env.py --office` installs the same packages with the office runtime preflight;
the full installer additionally prepares private profiles and verifies startup readiness.
For Windows, first use the [verified runtime candidate and diagnostic](docs/WINDOWS_RUNTIME.md);
stock Python's version label does not guarantee a patched SQLite library. Office setup now
checks the selected interpreter before creating an environment or installing packages.
Recreate `.venv` on the Mac. After configuring protected settings, approved endpoints and
signed metadata review, start automatic resource preparation and monitoring:

```text
python -m nl2sql office --settings /approved/office.json --env-file /approved/office.env
```

See OPERATIONS.md for first-time certification. You do not build graph/vector indexes by
hand. FAISS is removed; configured metadata vectors use embedded SurrealDB. The launcher
never invents business definitions/access approval and downloads no model weights.


Architecture remediation (24 October 2026) adds versioned storage upgrades, typed model
clarification, current-scope follow-up context, schema-text and estimated projection-memory preflight and
shared request/error handling. The office template defaults to exact/BM25 retrieval; embeddings
remain optional and are built automatically when approved and enabled. Use private copies of
`config/office.example.json` and the numbered `config/office.env.example`.

Office setup checks FTS5 and the actual linked SQLite library for the WAL-reset fix. Python's version
label alone is insufficient; use an approved Python 3.13 build with SQLite 3.51.3+ or a documented
patched backport. Restricted startup rejects source-tree/synchronized/relative storage paths.
No company Oracle/model connection, weights download, transfer, push or deployment is performed
by these fixes. Consult OPERATIONS.md before upgrading an existing metadata/session repository.

The [remediation report](reports/architecture-remediation-2026-10-24.md) maps all 16 review
findings to implementation, tests and the remaining office qualification requirements.

Office qualification now targets a 100000-token model in both configuration examples.
Eight bounded chat turns share one inference slot initially; exact templates bypass the
model slot while retaining execution/session/per-user protections. These are provisional
settings, not measured office capacity. See OPERATIONS.md for the real-model/hardware gates.
The [office qualification update](reports/office-qualification-update-2026-10-24.md) records
the six roadmap items, completed local work and pending external qualification.
