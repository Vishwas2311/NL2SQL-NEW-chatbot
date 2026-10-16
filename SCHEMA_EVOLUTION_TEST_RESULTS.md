# V4.3 evolution evidence

Commands: `.venv/Scripts/python -m pytest -q`, `python scripts/check.py`, and
`python scripts/schema_evolution.py`. Final gate output is recorded in reports/quality-check-v43.txt.
Final full run: 249 passed, 89% branch-inclusive coverage, all six quality gates passed.
The run completed in 125.47 seconds for Pytest, with one upstream deprecation warning.
No corporate database, real model, native FAISS or UI browser was used.

| Required scenario | Executable evidence |
|---|---|
| Initial related tables, discovery, graph, BM25 | discovery/lifecycle tests; actual bootstrap |
| Optional embedding/index build | Toy encoder + injected native contract; no real encoder/native run |
| Certified publication and actual NL query | Lifecycle/CLI/API; 175000.50 / 75000.00 |
| New table, column and FK | Actual SQLite DDL; no new semantics/grants |
| Composite-key change | Inventory mutation; dependent quarantine |
| Column type/precision/nullability/removal | Inventory mutations; unaffected reports retained |
| Breaking metric mapping | Pending verification; cannot approve |
| Changed synonym/view | Signed new corpus; approved meaning preserved until publish |
| Unauthorized metadata addition | Unmapped source never enters semantic catalog/access |
| Changed grants during execution | Actual query result discarded after revocation |
| Ambiguous joins | Catalog/graph rejection |
| Failed graph/index/runtime build | Active version and working queries preserved |
| Failed activation | Source TOCTOU, stale CAS and expired worker rejected |
| Concurrent questions during refresh | Old/new pinned provenance; same golden results; old pool drains |
| Restart/recovery and compatible rollback | Reverified durable pointer and approvals |
| Incompatible/revoked-grant rollback | Refused |
| Unchanged schema / row-only updates | No index rebuild; updated amount appears in answer |
| Source restored after quarantine | New reviewed candidate clears block |
| Scheduler | Disabled default, due-time singleton, bounded retry and safe logging |
| Private exports | Marker/subtree and copied payload exclusion |
| Oracle names and money | Quoted owner/name, native Decimal/date binds, 38-digit value |
| Dictionary permissions | Missing optional evidence recorded; required visibility fails closed |

The independent synthetic benchmark has 30/30 correct template answers, p50 40.07 ms, p95 50.32 ms,
initial build 346.26 ms and bootstrap/approve/publish 655.83 ms. Traced Python peak: 2,253,930 bytes.
Row-only update returns 175001.50 with no rebuild; added column stays pending/ungranted. See the
machine-readable report for exact measurements. These local/traced timings are not production SLOs.

The separate 46-question workflow corpus passes all 46 cases: 37 correct supported results and
9 safe refusals. It uses deterministic scripted plans, not real Gemma inference. Optional toy-hybrid
tests deliberately retain one unsafe unknown-question regression to demonstrate promotion must
compare business results. No real hybrid uplift or model token score is claimed.

One upstream Starlette/httpx deprecation warning remains. Pinned approved dependencies were retained;
no unapproved httpx2 dependency was added to silence it.
