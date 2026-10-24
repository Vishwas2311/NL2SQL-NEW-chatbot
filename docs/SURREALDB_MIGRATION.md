# SurrealDB migration — 24 October 2026

The user approved this replacement after the isolated office probe passed. The backend
now pins `surrealdb==2.0.0` for graph traversal and optional exact-cosine metadata vectors.
LadybugDB imports, driver stubs, buffer settings, DLL hooks and CI prerequisites are removed.
SQLite metadata/session authority, Redis admission, Oracle adapters, model contracts,
independent SQL validation, signed capabilities and the frozen UI keep their roles.

## Storage and worker ownership

Each approved catalog produces `data_dir/graphs/<catalog-digest>.surreal.json`, a private,
canonical snapshot containing graph format, catalog identity, nodes, joins and lineage.
Publication uses an exclusive reservation, a flushed/fsynced temporary file, native
validation and atomic rename. Existing files are never overwritten. Readers compare the
entire snapshot against their approved catalog before opening a native store; a changed,
truncated or oversized file fails closed. File contents are never interpreted as queries.

Each runtime handle populates its own embedded `mem://` SurrealDB graph. Graph links are
native SurrealDB relationships; frontier queries bind allowed pairs before discovery.
Per-partition vector projections apply allowed metric keys before ordering/limiting exact
cosine scores. Serialized access and idempotent close preserve lease-based retirement.
These are rebuildable projections, not an additional business/access authority.

This deliberately avoids a shared persistent SurrealKV directory: its datastore lock
allows only one owning process. Immutable snapshots support the existing API workers and
external monitor without adding a server. [Official embedded ownership documentation](https://surrealdb.com/docs/reference/rust/embedding#logging-and-one-process-per-datastore).
The implementation uses the [pinned Python 2.0.0 SDK](https://pypi.org/project/surrealdb/2.0.0/),
not features inferred from newer SDKs or a separate embedded beta package.

## Upgrade procedure

1. Stop the office supervisor, all API workers and monitor. Back up the protected SQLite
   authority, approved catalogs, signatures, settings, cache and graph artifacts.
2. Install the updated pinned lock files into a fresh Python 3.13 virtual environment on
   approved local storage. Keep the previous environment for rollback. Do not copy a
   virtual environment from another machine or modify Program Files/native system DLLs.
3. Remove `graph_buffer_mb` and `graph_native_dir` from protected settings JSON and remove
   `NL2SQL_GRAPH_BUFFER_MB`, `NL2SQL_GRAPH_NATIVE_DIR` and test DLL-directory overrides
   from the selected environment/launch configuration. JSON settings reject removed keys.
   The application's existing `.env` is never rewritten by setup.
4. Keep restricted runtime storage outside the source tree, OneDrive and network shares.
   Existing `.lbdb` files stay untouched; the new adapter neither reads nor converts them.
   It rebuilds graph snapshots from approved metadata. No authoritative rows are migrated.
5. Managed installations must stage a fresh candidate with the new code, inspect it and
   obtain matching signed reviews through the existing steward/security workflow. The
   SurrealDB backend changes search/vector fingerprints even for the same catalog. Use
   the existing `metadata approve` / `metadata publish` workflow or `office --approval-file`
   with the exact new candidate's signed manifest. Never edit old manifests/fingerprints,
   reuse old candidate signatures or use synthetic `sign-demo` for office metadata.
   Preparation must return `state=ready` before serving. Discovery alone cannot approve it.
6. Run the mandatory checker from the repository root, once per command:

   ```powershell
   .\.venv\Scripts\python.exe -m pip check
   .\.venv\Scripts\python.exe scripts/check.py
   ```

   Then qualify approved Oracle, identity and SLM connections on the actual office runtime.
   Local synthetic tests never substitute for these checks.

## Limits, recovery and rollback

No SurrealDB hard allocator/RSS cap is claimed. The retained `retrieval_max_native_mb`
setting checks a conservative 32 MiB-per-vector-partition admission estimate; text,
component, dimension and record limits still apply. Measure RSS/startup/latency with
actual catalogs, encoders, worker counts and retained versions before office release.
No weights, model servers, ANN index or remote graph endpoint are introduced.

Corrupt snapshots fail closed. With workers drained, restore a verified snapshot or
rebuild from its approved catalog. Inspect abandoned `.building` reservations and temporary
files under maintenance before removal. Never delete files based on one worker's leases.

For rollback, stop workers and restore the previous code/environment with its compatible
approved publication. Check current physical compatibility and grants first. Never restore
revoked access or old authority over newer approvals. Keep `.lbdb` and new graph artifacts
until the rollback window and every worker's retirement are complete.

The SurrealDB core license differs from LadybugDB; organizational dependency/license
approval remains an office release requirement. [Vendor license](https://surrealdb.com/license).
The separate office SQLite preflight is unchanged: replacing the graph engine does not
patch Python's bundled SQLite library.
