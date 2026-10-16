# Ponytail V4.3 audit and review

What this change does: It turns physical dictionary discovery into a pending, reviewed metadata
candidate and publishes a complete pinned runtime only after signature, compatibility and readiness
checks. Queries retain exact financial values, current permissions and owned session contracts.

Applied the installed official coding, audit and review skills manually. Read the source-to-candidate,
signature-to-publication, pin-to-query, retry/rollback, session/auth and export paths. Assumed load:
bounded local workers sharing a protected SQLite WAL store, a separate scheduler and four read
connections. No native FAISS, enterprise Oracle or real model performance assumption was made.

Resolved findings from implementation review:

1. PRAGMA FK sequence numbers could move when adding a key. Stable identities now use endpoints
   and column pairs, preventing an unrelated FK from appearing changed.
2. Returning to a still-leased bundle could overwrite lease bookkeeping. Entries now use separate
   lease identities; old handles close only after their own requests drain.
3. Rollback could race a physical change during readiness. A second fingerprint check now rejects it.
4. A restored source could remain quarantined because unchanged metadata skipped staging. Restoration
   now creates a reviewed candidate; tested approval/publication clears quarantine.
5. Physical-only bootstrap could not attach settings later, and status needlessly opened sessions.
   Sync now persists explicitly supplied settings; status is read-only and does not load execution settings.
6. Repeated identical pending discoveries could accumulate candidates. Healthy matching pending
   candidates are reused; failed builds remain retryable.
7. Copied inventory/approval JSON could enter portable exports outside the default private directory.
   Private markers, subtree pruning and recognizable payload checks now exclude it.
8. Oracle numeric entity IDs could coerce label text to NUMBER. Key and label predicates now have
   separate typed binds, and nonnumeric names do not enter the numeric comparison.
9. An older approved candidate could replace newer grants through ordinary publication. Candidates
   now bind the base publication and must be restaged/reviewed after any intervening activation.
10. Changed policy mappings could leave old history visible under an unchanged principal revision.
    Policy fingerprints now require a fresh revision and matching grants; saved rows are redacted.

11. Query-pool initialization could expose a raw driver exception. It now raises a safe application
    failure; an injected driver-failure test checks that private diagnostic text is absent.

These fixes have targeted regression tests. Final gates: 249 tests, 89% coverage, all checks pass. No remaining concrete must-fix defect was identified for
the declared local synthetic scope. Independent compiler/validator contracts are intentionally separate.

Verdict: Ship for the declared local synthetic scope after the recorded gates pass.
Not checked: Real Oracle/Gemma/encoder/native FAISS, corporate identity/trust/VPD, multi-node capacity,
hosted CI, browser integration, deployment and actual Ponytail hook execution.
