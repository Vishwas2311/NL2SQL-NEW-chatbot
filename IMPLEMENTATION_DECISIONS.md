# Development hardening decisions (2026-10-16)

- One-command office preparation uses the standard-library `venv` module and existing
  `requirements-core.lock`. Oracle and development dependencies stay separately selectable.
  `.env` creation uses exclusive file creation so existing settings cannot be overwritten.
  The application continues to require explicit `--env-file .env`; no implicit dotenv loading.

- Configuration precedence: process environment > explicitly selected dotenv > JSON > defaults.
  No implicit dotenv search. Oracle/discovery secrets continue to use approved environment injection.
- Use one model factory and encoder identity across administrative and application construction.
  Hosted inference is a separate HTTPS adapter, requiring explicit synthetic egress authorization
  and a synthetic assembled catalog. No provider was contacted during implementation.
- Cache embeddings by content hash plus provider/model/version/dimension/normalization identity.
  Optional JSON snapshots require marked restricted storage; corruption triggers recomputation.
  Cache checksums detect corruption; signed bundle digests remain the compatibility authority.
- Ordinary restart loads and verifies the published snapshot. An explicit startup reconciliation
  gate remains available; office deployment must choose its freshness/physical verification policy.
  Scheduler remains disabled by default and outside API workers.
- Logical join proposals require ordered pairs, type/grain/partition evidence and a review reference.
  Discovery does not generate that evidence. Publication still requires configured signed reviews.
- Retain synchronized FTS connections per grant partition. Measure concurrency before adding pools
  or asynchronous infrastructure. Resource construction now coalesces builds outside the cache lock.
- General SCD2/windows/period comparisons need certified semantics and remain office-pending.

Final verification: 323 tests, 89% coverage and all six quality gates passed.
SQLite rejects native integer binding overflow at its adapter boundary, while Oracle compilation
retains the wider exact NUMBER contract. Context byte budgets count entries once.

# Historical V4.3 decisions

The V4.3 lifecycle is implemented. See SCHEMA_IMPLEMENTATION_REPORT.md, SCHEMA_EVOLUTION_TEST_RESULTS.md and ORACLE_BOOTSTRAP_RUNBOOK.md. The V4.2 record below is historical; its former missing metadata workflow has been added.

# Implementation decisions - 2026-10-16

1. The latest audit-fix request authorizes continued backend coding; original scaffold-only stopping
   guidance is superseded. Frontend assets, company systems, weights, publication and deployment stay outside scope.
2. Reproduced 122 passing tests and one missing-manifest failure before changing features. Restored
   the absent original design-pack directory from its existing Git index. No expected hashes were
   regenerated and no preservation test was weakened. Restored baseline passed all gates, 123 tests.
3. EWS errors reuse one compatibility formatter for handler and body-limit paths. Safe top-level
   detail/message/response/results fields coexist with the internal structured error; SQL/provider details stay private.
4. Keep immutable catalog/plan contracts and independent security validation. New typed operators are
   certified difference/percentage metrics, half-open date ranges, explicit fiscal start calendar,
   snapshot ranges retaining reporting-date grain, aggregate ranking and certified multi-fact composition.
5. Multi-fact composition preaggregates each source to the certified customer grain before LEFT joins.
   Tenant/region/status policy runs in every source and outer customer scope. No inner result limit
   truncates totals. Only primitive SUM/COUNT are accepted; zero-count coalescing is explicit.
   Historical current-only account counts cannot accompany historical loan snapshots.
6. Ratio numerators/denominators and average sums/counts stay integer in SQL. Decimal formatting performs
   division without float money. Zero/missing ratio denominators yield null. Derived dependencies must
   have compatible units/scales/time grain and primitive same-source sums. Numeric aggregates
   require integer columns, and dimension types must match physical mappings. Models select metric IDs only.
7. ROW_NUMBER uses dimension tie breakers; DENSE_RANK preserves metric ties. Both run after aggregation,
   before rank/global result limits. Average/ratio sorting/HAVING/ranking remain unsupported.
8. Leaf AST validation remains separate from compilation. Ranked, composite and simple aggregate CTE
   wrappers are compared against independent complete contracts, then every source aggregate is
   independently validated. Bind metadata is inferred from approved columns and included in signatures.
   Raw model SQL, arbitrary functions, joins, CTEs, UNION and procedural fallback remain disabled.
9. Exact alias spans suppress shorter nested aliases, while a shared alias still requires clarification.
   Scope partitioning precedes both lexical/vector ranking. Optional in-process embedding fusion adds
   no dependency/server and is disabled by default. Startup failures close constructed indexes.
10. Paired retrieval experiments use identical questions, catalogs, scopes, scripted plans and independent
    expected rows in fresh databases. A toy encoder tests fusion and detects a regression; it is not
    semantic quality evidence. No approved encoder or FAISS is installed.
11. Private HTTP inference reuses its client, bounds structured output, retries and deadlines, and
    verifies exact configured runtime identity, assistant role and no tool calls. Model metadata/text
    is untrusted. Formula/component dependency IDs stay internal even when a derived metric is granted.
    No real runtime was configured or contacted; Gemma availability remains unverified.
12. Oracle stays explicitly gated and outside normal SQLite startup. Native DATE binds derive from
    certified column mappings. Exact NUMBER, date/time serialization, schema, bytes/rows, cancellation,
    deadlines and cleanup are driver-contract tested with an injected pool. Failed context cleanup
    discards connections; no confidential/real Oracle connection was attempted. DBA VPD and resource
    manager/preflight qualification are required before selecting the adapter in enterprise startup.
13. Preserve Python 3.13.16, approved dependencies and quality thresholds. No test, coverage exclusion or
    broad lint suppression was added to hide defects. pip-audit is isolated in ignored `.local/audit-tools/`;
    runtime requirements are unchanged. Its public advisory lookup contains package names/versions only.
14. Existing v1 metadata and local data remain intact. New `catalog-v2.json` and CLI default support fresh
    v2 installs; the isolated `.local/audit-v2/` demo exercises new fixtures without migrating old data.
15. Ponytail 5.2.0 official installed manifest and enabled plugin setting were verified. Three trust-hash
    records are now present in Codex configuration; this agent did not write or bypass them. No /hooks
    runtime evidence was supplied, so actual lifecycle execution is unverified. Official coding,
    audit and review skills were read/applied manually, with reports separate from tool quality gates.
16. Local token/JWT authentication, quotas and session storage assume one managed process. Corporate
    live revocation/SSO, distributed quotas/idempotency, encrypted retention/purge and release approval
    are not supplied by local tests. No commit, push, hosted CI, UI integration or deployment occurred.
17. The standard-library project exporter uses atomic output and excludes runtime credentials, caches,
    binaries and earlier exports. It is regenerated after documentation and report updates.

## V4.3 decisions

Physical discovery cannot certify business meanings. Keep existing layers and dependencies; use private immutable specifications, configured review signatures and SQLite CAS rather than another service. No automatic approval, model-based drift detection, raw SQL fallback, weight downloads or deployment. Keep exact financial divisor/precision and source names explicit. Optional FAISS uses lazy approved injection; no native dependency added. Rollback denies older grants/policies rather than silently merging permissions.
