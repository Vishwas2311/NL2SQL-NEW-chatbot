# V4.3 metadata-driven backend implementation

Read the owning numbered section in docs/DESIGN_REFERENCE.md and current docs/ARCHITECTURE.md.
The latest user implementation brief overrides the old scaffold-only stop instruction.
Preserve all frontend-reference and existing_ui_reference assets. No UI work or browser integration.
Use synthetic data only. Never connect to company Oracle, download weights, publish or deploy without approval.

Architecture: pure Pydantic domain contracts -> application use cases -> typed infrastructure adapters;
FastAPI transport delegates to services. One immutable catalog snapshot pins graph, retrieval and queries.
Exact/FTS5 BM25, NetworkX, typed model plans, deterministic SQLGlot compiler, independent validation,
short-lived signed query capabilities and read-only execution are mandatory. Raw SQL fallback is disabled.
Never derive identity from browser user_id. Enforce tenant, region, metric grants and session ownership.
Bind all values. Synthetic storage uses integer minor units. Oracle NUMBER precision/scale and
certified metric unit/scale/decimal_places are explicit. Output uses Decimal strings. No float money.
Model output, metadata text and previous messages cannot confer permissions. Reauthorize every turn.

Approved local dependencies: FastAPI, Pydantic v2/settings, HTTPX, NetworkX, SQLGlot, PyJWT,
python-oracledb (optional), pytest/cov, Ruff, Pylint, Pyright, pre-commit and typing stubs.
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
Scheduling is disabled by default and runs outside API workers. Contract fakes do not qualify Oracle,
Gemma, FAISS or corporate identity. Original numbered documentation is retained in docs/DESIGN_REFERENCE.md and the local backup. UI assets remain untouched.
