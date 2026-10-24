# Application review before pushing the SurrealDB migration

24 October 2026. Reviewed application code through commit `3fbb583` on
`codex/surrealdb-migration`, against `9f7112d`.

What this repo does: A governed NL-to-SQL backend retrieves certified metadata,
builds typed plans, independently validates compiled SQL and executes read-only
queries. SQLite retains metadata/session authority; embedded SurrealDB holds
derived graph/vector projections. The intended office workload is about 20 users,
with eight active chats and one inference call initially; these are provisional
budgets, not measured office capacity.

## Review scope and method

Applied Ponytail audit/review guidance and the relevant Agent Skills quality,
Git workflow and regression-testing guidance. Independent read-only reviews
covered storage/lifecycle and the application request/security flow. The existing
Graphify map was queried for navigation; its older engine references were checked
against current source rather than accepted as implementation evidence.

Traced API authentication/admission, typed planning, entity lookup, deterministic
compilation, independent SQL capabilities, read-only execution and owned sessions.
Reviewed graph/vector snapshots, parameter binding, permission filtering, native
cleanup, concurrent resource adoption/retirement, signed manifest compatibility,
early runtime setup checks, dependency locks, CI and operating documentation.
This was a risk-focused source review across the backend layers, not a claim to
have manually inspected every repository line or performed a penetration test.

## Findings addressed

1. **Unexpected embedding-checkpoint errors leaked shared search resources.**
   `RuntimeFactory._search` created a retriever before checkpointing, but its failure
   handler covered only retriever construction. An injected checkpoint RuntimeError
   left the retriever open and a concurrent caller waiting until `INDEX_BUSY`.
   Normal checkpoint disk/path errors were already caught by the encoder.
   The existing ExitStack pattern now owns the retriever until preparation succeeds;
   failure closes it and completes the shared future exceptionally. Both callers see
   the failure, the cache entry is removed and a subsequent attempt can succeed.
   The new concurrent regression failed before the fix and passed afterward. The
   existing coalesced-build test also passed. An independent reviewer checked the fix.

2. **Older documentation overstated native memory enforcement.**
   Corrected README, walkthrough and configuration wording: vector partition memory
   is an admission estimate, not a SurrealDB allocator cap or process RSS limit.
   Worker count and overlapping resource versions still multiply memory costs.

No further confirmed blocking findings were identified in the reviewed paths.

## Fresh local verification

The complete mandatory `python scripts/check.py` run exited **0**, using the
isolated qualified Windows runtime: Python **3.13.17**, SQLite **3.53.1**, working
FTS5 and OpenSSL **3.5.9**. `pip check` reported no broken requirements.

- Ruff correctness/import checks and formatting: passed, 175 Python files formatted.
- Pylint: **10.00/10**. Strict Pyright: **0 errors, 0 warnings**.
- Pytest: **490 passed, 9 skipped, 1 warning**, in **1182.03 seconds**.
- Branch-inclusive coverage: **90%**.
- All three pre-commit checks: passed.
- A separate in-process mutation bypassing the SQLite patch guard made its
  existing preflight test fail, confirming that the guard is tested. No source or
  production setting was changed by that mutation.
- Git whitespace checks and object integrity inspection passed. No UI files changed;
  private environment files, runtime archives and databases remain outside the commit.

The nine skips are explicit real-Redis tests. Docker's Linux daemon was unavailable
locally; no company Redis was contacted. The dedicated hosted Redis job remains the
place to verify those tests after push. The single warning is the existing upstream
Starlette TestClient/httpx deprecation; dependencies were not changed to suppress it.

Raw logs remain ignored under `.local/runtime-qualification/`: `check-push-final.log`,
`search-regression-red.log`, `search-regression-green.log` and
`runtime-mutation-review.log`. An earlier intermediate checker was deliberately
stopped to apply the reproduced fix; the exit-0 result above is the subsequent full run.
Static pre-commit hooks resolve the original root `.venv`; explicit quality modules
and full pytest ran under the isolated patched runtime, with the same locked packages.

## Release limits

No office laptop, corporate Oracle/identity, real SLM/encoder or representative
hardware capacity was qualified here. No UI/browser integration or deployment was
performed. Existing `.env`, original `.venv` and runtime data were preserved.

Office transfer still needs approval of the exact runtime described in
`docs/WINDOWS_RUNTIME.md`, a fresh environment after validating it, protected storage
and fresh signed metadata publication as described in `docs/SURREALDB_MIGRATION.md`.
A source-code pull cannot change the SQLite library inside an existing interpreter.

Verdict: locally verified for review and synthetic testing; office qualification
remains required. Hosted CI results are separate evidence to inspect after pushing.
