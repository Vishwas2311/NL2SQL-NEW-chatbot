# V4.3 metadata-driven backend implementation

Read the owning numbered section in docs/DESIGN_REFERENCE.md and current docs/ARCHITECTURE.md.
Use docs/APP_WALKTHROUGH.md for the verified system explanation and docs/STRUCTURE.md for ownership.
LadybugDB is the runtime graph projection; SQLite retains metadata/session authority, Redis
only coordinates admission, and office Oracle/model/UI integration must not be inferred as live.
The latest user implementation brief overrides the old scaffold-only stop instruction.
Preserve the canonical UI/*/existing_ui_reference assets. The duplicate frontend-reference copy
was removed at the user's request on 2026-10-20; its unique test was retained beside the canonical UI.
No UI content changes or browser integration.
Use synthetic data only. Never connect to company Oracle, download weights, publish or deploy without approval.

Architecture: pure Pydantic domain contracts -> application use cases -> typed infrastructure adapters;
FastAPI transport delegates to services. One immutable catalog snapshot pins graph, retrieval and queries.
Source ownership is documented in docs/STRUCTURE.md. Domain/application code must not
import infrastructure or transport; bootstrap wires adapters and owns resource lifecycle.
Exact/FTS5 BM25, LadybugDB, typed model plans, deterministic SQLGlot compiler, independent validation,
short-lived signed query capabilities and read-only execution are mandatory. Raw SQL fallback is disabled.
Never derive identity from browser user_id. Enforce tenant, region, metric grants and session ownership.
Bind all values. Synthetic storage uses integer minor units. Oracle NUMBER precision/scale and
certified metric unit/scale/decimal_places are explicit. Output uses Decimal strings. No float money.
Model output, metadata text and previous messages cannot confer permissions. Reauthorize every turn.

Approved local dependencies: FastAPI, Pydantic v2/settings, HTTPX, LadybugDB, SQLGlot, PyJWT,
python-oracledb (optional), pytest/cov, Ruff, Pylint, Pyright, pre-commit and typing stubs.
Redis and redis-py were authorized for shared admission across concurrent VM API workers
on 2026-10-20. Redis does not replace current grants, durable sessions or metadata authority.
No extra model servers, vectors or graph databases without measured need and approval.
Run python scripts/check.py; security, compiler goldens and API contract tests are required.
Keep docs/ARCHITECTURE.md, docs/CONFIGURATION.md and docs/OPERATIONS.md accurate.

Ponytail: official DietrichGebert/ponytail installation approved by user on 2026-10-16.
Apply its read-first, reuse, smallest-complete-change and risky-logic-test guidance.
Do not claim lifecycle hooks active without evidence from /hooks; never edit trust records to bypass review.
Ponytail does not replace quality tools. Use its installed audit/review skill when available.

V4.3: dictionary discovery creates evidence, never business or access certification. Keep private
profiles, inventories, approvals and snapshots in marked restricted storage. Stage changes, verify
configured signatures, build compatible resources and atomically publish one durable version.
Pin requests, drain retired leases, reauthorize active requests and never roll back revoked grants.
Scheduling is disabled by default and runs outside API workers. Contract fakes do not qualify Redis, Oracle,
Gemma, real encoders or corporate identity. Original numbered documentation is retained in docs/DESIGN_REFERENCE.md and the local backup. UI assets remain untouched.

2026-10-23: user requested removal of FAISS and automatic office resource preparation.
FAISS/factory adapters are removed. Configured embeddings use embedded Ladybug exact-cosine
projections, built automatically with compatible runtime resources. `office` prepares
approved Oracle resources and supervises a separate monitor; bare `serve` never starts
scheduling. Preserve signed certification and synthetic-only local tests. Restricted HTTP
planning requires same-origin runtime token counting with output reserve.
