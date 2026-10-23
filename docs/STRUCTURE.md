# Code structure

The [system walkthrough](APP_WALKTHROUGH.md) maps these packages to metadata setup, live
requests and monitoring. Keep the ownership map and that explanation aligned when changing code.

The package is organized by ownership and dependency direction. Public HTTP routes,
CLI commands, serialized catalogs and session records retain their existing contracts.
Internal Python imports moved to the owning packages; no legacy forwarding modules
were added. `python -m nl2sql` remains the stable command entry point.

```text
backend/nl2sql/
  domain/                 # Pydantic business, physical, session and metadata contracts
  application/
    chat.py               # Authenticated reporting orchestration over one pinned Catalog
    inference.py          # Model call admission, independent from full-turn admission
    routing.py            # Catalog templates and bounded deterministic follow-ups
    results.py            # Exact Decimal financial row formatting
    sessions.py           # Owned session operations and response-time reauthorization
    ports.py              # Identity, query, session, retrieval, model and quota contracts
    context.py            # Authorized model-context construction
    catalog.py            # Semantic validation and certified join policy
    graph.py              # Typed runtime traversal port and pure structural checks
    query/                # Plan validation, compiler and independent SQL validator
    metadata/             # Certification, drift, publication/refresh use cases and ports
  infrastructure/
    storage.py            # Ordered SQLite upgrades and sanitized storage failures
    http_policy.py        # Shared private endpoint/client policy
    graph.py              # Immutable embedded LadybugDB projections and native lifecycle
    auth.py               # Local token/JWT identity adapter
    sessions.py           # Transactional SQLite session adapter
    rate_limit.py         # Memory/Redis rate quotas, active-chat leases and capability probe
    databases/            # Read-only SQLite and gated Oracle execution/context adapters
    metadata/             # Discovery, repositories, signatures, catalog loading and builds
    retrieval/            # SQLite FTS5, embeddings and optional native vector adapters
    inference/            # Disabled, scripted and HTTP model providers
  api/                    # FastAPI transport, public schemas and middleware
  bootstrap/              # Composition roots, request leases and spawned-worker factory
  cli/                    # Serve, configuration and metadata administration commands
  evaluation/             # Synthetic data and reproducible evaluation harnesses
  settings.py             # Validated application/environment configuration
  telemetry.py            # Request context and safe timing helpers
  __main__.py             # Thin python -m nl2sql entry point

tests/
  unit/                   # Isolated catalog, retrieval and quota behavior
  contracts/              # API shapes and injected provider/Oracle contracts
  integration/            # Real local SQLite/Ladybug/workflows; explicit local Redis suite
  security/               # Permission, compiler mutation and capability denials
  evaluation/             # Evaluation harness checks
  tooling/                # Import boundaries, worker/setup, export and UI preservation
  conftest.py             # Isolated synthetic fixtures and environment guard

config/                   # Office/VM examples and optional local Redis Compose configuration
metadata/synthetic/       # Fictional catalogs only
scripts/                  # Quality/evaluation entry points and isolated Redis setup
docs/                     # Current guides plus retained original numbered design
reports/                  # Sanitized measurements and dated reviews
UI/.../existing_ui_reference/  # Sole unchanged UI reference and original hashes
```

## Dependency rules

- Domain models import only domain code and supporting standard-library/Pydantic
  types. They never open files, connect to databases, call Redis or import FastAPI.
- Application use cases depend on domain contracts and typed ports. They do not
  import infrastructure, API, bootstrap, CLI or synthetic evaluation code.
- Infrastructure implements ports and can depend on domain/application contracts.
  Tests also forbid it from importing bootstrap, API, CLI or evaluation modules.
  Driver annotations are narrowed at explicit adapter boundaries.
- API code maps HTTP to use cases and typed resources. It does not construct
  database pools, model clients, indexes or Redis clients.
- Bootstrap owns concrete construction and cleanup. It is the appropriate place
  to select adapters, prepare runtime bundles and wire the application factory.
- CLI and evaluation code may compose real adapters for explicitly selected
  administrative or synthetic operations. Metadata publishing remains outside
  request handlers and outside API worker scheduling.

`tests/tooling/test_architecture.py` enforces the main import boundaries. Strict
Pyright, Ruff, Pylint and the existing security/compiler/API suite remain mandatory.
Package `__init__.py` files identify packages without broad re-export lists.

## Where to make a change

| Change | Owning location |
|---|---|
| New public request/response field | api/schemas.py and contracts tests |
| New business or permission contract | domain/ and application validation |
| New supported SQL operation | application/query/ plus independent negative/golden tests |
| New database/provider/cache implementation | infrastructure/ behind an application port |
| Resource selection or lifecycle | bootstrap/ |
| Settings and safety constraints | settings.py, config examples and configuration guide |
| Metadata discovery/publication behavior | application/metadata/ and infrastructure/metadata/ |
| Concurrency/Redis behavior | infrastructure/rate_limit.py and quota/real-server tests |

Keep credentials, runtime databases, real inventories, approval payloads, snapshots
and model files in approved restricted storage outside the source tree and cloud
synchronization. Folder names and Git ignores are not filesystem permissions.

## Redis scope

The VM profile uses Redis for rate quotas and global/per-principal active-chat
leases shared across workers. Durable conversation
state and metadata authority keep transactional persistence; Redis contains no
business result cache, identity grants or approval authority. This distinction
preserves current revocation and publication controls while enabling shared
admission. See CONFIGURATION.md and OPERATIONS.md for the supported launcher,
Redis prerequisites, failure behavior and qualification limits.

`typings/ladybug/__init__.pyi` narrows the native API used by the adapter for strict
static analysis. No native driver is imported from application or domain code.

`cli/office.py` owns the foreground supervisor; `cli/metadata.py` owns automatic preparation
through signed lifecycle operations. `infrastructure/inference/token_budget.py` preflights
runtime tokens. `infrastructure/retrieval/vector_index.py` owns embedded Ladybug exact-cosine
projections, replacing the removed FAISS adapter and vector-factory selection path.


2026-10-24 ownership additions: `domain/planning.py` owns model decisions, clarification and
pending questions; `bootstrap/office_checks.py` owns offline SQLite/storage prerequisites.
Transport owns HTTP status mapping; domain failures use application categories. Chat receives
its independent validator explicitly; the execution port no longer exposes it. The architecture
test resolves relative imports and verifies that detection with a synthetic violating import.
The stock office embedding modes are disabled/private_http. Approved direct local Python
providers remain integration seams for custom process composition, not automatic weight loaders.
