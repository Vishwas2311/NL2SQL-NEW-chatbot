# Discovery design

MetadataDiscoveryProvider.discover returns immutable PhysicalInventory. OracleDiscovery is the
authorized office adapter. SyntheticDiscovery and FileDiscovery exercise the same staging contracts.
Copied Oracle JSON requires live reconciliation; possessing an offline file cannot certify a live schema.

Approved-environment, owner and network flags are checked before acquiring a connection. Discovery
credentials are SecretStr environment settings, separate from business-query credentials. Owner
values are bound and SQL projections fixed. Business rows, default expressions and statistics are
not fetched. Cumulative row/byte/deadline budgets, a read-only transaction and rollback/release/drop
cleanup apply. Routine diagnostics use safe codes.

The workflow discovers, fingerprints, classifies, computes dependencies, reconciles semantics, builds
compatible artifacts and stores a pending immutable candidate. Physical-only bootstrap remains
useful without semantics but cannot publish. Gemma never detects schema changes.

Official references: [ALL_TAB_COLUMNS](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/ALL_TAB_COLUMNS.html),
[ALL_CONSTRAINTS](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/ALL_CONSTRAINTS.html),
[python-oracledb connection API](https://python-oracledb.readthedocs.io/en/latest/api_manual/connection.html).
Actual corporate privileges and versions require DBA qualification.
