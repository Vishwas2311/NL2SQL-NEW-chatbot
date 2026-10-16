# Certified view coverage

| Synthetic view | Semantics | Policy |
|---|---|---|
| loan_snapshot | Loan-grain dated snapshot | Tenant, allowed region, active status |
| account_current | Current accounts only | Tenant, allowed region, active status |
| payment_events | Events within ISO/fiscal bounds | Tenant, allowed region, active status |
| customer_portfolio | Independently preaggregated facts at customer grain | Component and outer scope |

ScopePolicy maps tenant column, scope dimension, protected regions/scopes claim and optional status.
Oracle database_context requires separately approved read-only grants and DBA context apply/reset
procedures. SQLite cannot stand in for that policy. EntityMapping declares exact ID/label columns
and direct scope mappings. Numeric IDs are bound without comparing arbitrary labels to NUMBER.

Four synthetic views are covered. No corporate view is certified. Missing physical uniqueness or
incomplete definition evidence remains pending; approval cannot bypass reconciliation. Unsupported
operators and grain combinations reject explicitly.
