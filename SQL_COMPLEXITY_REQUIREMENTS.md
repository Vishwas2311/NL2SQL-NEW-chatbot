# Typed SQL capability contract

Supported: certified multi-table/composite joins; multiple measures/dimensions; sum/count/min/max;
exact sum/count average; compatible differences/ratios/percentages; bounded AND/OR filters, NULL
tests and text IN; snapshots, event ranges and fiscal calendar bounds; GROUP BY/HAVING; deterministic
sort/limit; preaggregation CTE; independent multi-fact aggregates; ROW_NUMBER/DENSE_RANK/top-N.

SQLGlot maps internal IDs to quoted Oracle owner/object/column names. The independent validator
reverses approved mappings and checks the whole AST, policy, filter, time, grain, order and limit.
Recursive wrappers are checked independently. Raw SQL fallback/model SQL, unknown functions,
unapproved sources, incomplete keys and literal value insertion stay disabled.

Unsupported: arbitrary SQL/subqueries, general SCD2 interval joins, month/year-over-year operators,
RANK, LAG/LEAD, running totals and unrestricted window/expression syntax. Average/ratio HAVING
and sorting also reject explicitly. No verified company contract defines these added semantics;
they are not represented as implemented.

Settings can reduce max_metrics/max_dimensions (1..5), max_rows (1..1000), max_join_edges (0..6).
Filter depth/leaves and IN lists remain bounded. SQLite retains its stricter preflight checks.
Decimal-source execution and database-context policy require Oracle. Unit/divisor/output precision
are explicit. Native Oracle date/Decimal bind behavior is contract-tested without a live database.
