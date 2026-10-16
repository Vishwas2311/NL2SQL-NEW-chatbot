# Local operating runbook

Start with `python -m nl2sql serve` inside the pinned environment, or the explicit `.venv` interpreter
commands in README.md. Local settings are read from `.local/settings.json`; no environment credentials
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
principal grants differ from saved scope. Corporate real-time revocation and distributed limits need
the approved identity/deployment integration. Expired conversations are inaccessible; storage-level purge,
encryption, backups and legal retention are not provided by a scheduling daemon here.

Shutdown with Ctrl+C. Lifespan closes model HTTP clients, FTS indexes, business connections and sessions.
Back up `.local/sessions.db` through an approved SQLite-consistent procedure; protect local bearer files.
Do not copy `.local/` to source control. Development initialization refuses to overwrite existing data.

Oracle integration: use the gated adapter only in an approved synthetic Oracle test schema. Implement
DBA-owned OracleContextPolicy, prove pooled reset and DB-enforced scope, validate DATE/NUMBER/null/dialect
behavior, and repeat the injected-pool resource/cancellation/byte-budget cases against the real driver/server. No DDL is emitted by the chatbot.
EXPLAIN PLAN is not implemented and no cost-security guarantee is claimed.

Before enterprise release: complete OPEN_BLOCKERS.md, security/dependency/license review, actual CI,
real model/Oracle goldens, monitoring, rollback and source/data residency approvals. No deployment is
automatically triggered by the prepared workflow.
