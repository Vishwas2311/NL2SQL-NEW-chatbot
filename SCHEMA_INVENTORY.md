# Physical inventory

The local fixture contains five fictional tables: regions, customers, loans, accounts and payments.
SyntheticDiscovery reads sqlite_master and PRAGMA column/PK/unique/FK/index metadata through a
read-only connection. It never samples business rows. Daily amounts do not enter schema fingerprints.

OracleDiscovery reads bound, allowlisted owners against ALL_TABLES, ALL_VIEWS, ALL_TAB_COLUMNS,
ALL_CONSTRAINTS, ALL_CONS_COLUMNS and ALL_OBJECTS. Optional ALL_INDEXES, ALL_TAB_COMMENTS,
ALL_COL_COMMENTS, ALL_DEPENDENCIES and ALL_VIEWS.TEXT_VC enrich evidence. No company database
was contacted.

PhysicalInventory preserves raw owner/name/type, precision, scale, length, nullability, ordered key
pairs, referenced owner/constraint, validation status, comments, dependencies and DDL timestamps.
Canonical IDs combine a safe normalized stem and a hash of case-preserving raw identifiers.
Owner-qualified physical names remain separate from internal IDs.

Missing required visibility fails closed. Optional failures are recorded. Invalid objects, invisible
target keys, missing definitions and views exceeding bounded TEXT_VC evidence remain pending.
Names/comments cannot certify a join, amount meaning, tenant rule, currency or permission.

Detailed payloads live in private marked storage. This document contains synthetic names only.
There is no corporate inventory or claim of corporate schema coverage.
