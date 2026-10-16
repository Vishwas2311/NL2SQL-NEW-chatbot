# Relationship evidence

Synthetic keys are extracted from SQLite metadata. Oracle uses ordered ALL_CONS_COLUMNS and
ALL_CONSTRAINTS P/U/R records. A foreign key requires an enabled, validated referenced key within
approved visibility. Unknown targets remain unverified.

Reconciliation matches semantic relationships to exact physical objects and complete key mappings.
Target unique grain, compatible types, tenant partition pairs and source uniqueness for one-to-one
edges must hold. JoinGraph emits NetworkX edges only for certified catalog relationships after
reconciliation succeeds. Edges retain pairs, cardinality, temporal rule, evidence and catalog version.

The fixture has loans -> customers, accounts -> customers, payments -> customers and customers ->
regions. Composite joins include tenant_id; customer IDs overlap between tenants. Historical use
of current-only attributes is refused. Multi-fact reports aggregate facts before combining them.

Discovery adds no executable edge. Missing, ambiguous, fanout, incomplete composite and unverified
relationships reject. Path search stops after two paths. Effective-dated/SCD2 interval joins remain
unsupported until a certified temporal contract and compiler extension exist.
