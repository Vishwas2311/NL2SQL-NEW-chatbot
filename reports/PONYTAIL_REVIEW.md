# Ponytail change review - 2026-10-16

What this change does: It fixes the missing original preservation evidence and EWS error contract,
then extends the existing typed compiler and local adapter/evaluation tests. No UI or production
integration is introduced. The assumed load is one managed local process with four read connections.

The installed official `ponytail-review/SKILL.md` was read and applied manually. Reviewed connected
flows: API/errors/body limits, typed domain/catalog, retrieval/model context, entity resolution,
plan/proof validation, compiler/ranking/composite/binds, independent SQL validation/capabilities,
SQLite/Oracle execution/cleanup, sessions, initialization, evaluation and their callers/tests.
This report is a review result, not lifecycle-hook execution evidence.

The review found these issues during implementation; fixes and regressions are now present:

| Closed issue | Fix | Regression evidence |
|---|---|---|
| Current accounts could accompany historical loan balances | Reject mixed current/historical composite reports in planning.py | test_combined_current_accounts_cannot_be_presented_as_historical |
| Catalog allowed numeric aggregates on text or mismatched dimension kinds | Reject incompatible physical/semantic types before activation | test_catalog_type_contract_cannot_coerce_text_to_float_money |
| Derived formulas could mix scales or time semantics | Catalog requires compatible primitive units/scales/time and output contract | test_invalid_derived_metric_contracts_never_activate |
| Shared aliases could be accepted after enabling multiple metrics | Shared authorized alias requires clarification before model call | test_shared_alias_clarifies_even_with_a_covering_view |
| Encoder failure during index startup could retain open SQLite handles | ExitStack closes constructed indexes on startup failure | invalid encoder startup test plus lifecycle trace |
| Aggregate CTE outer source/projection validation was incomplete | Compare complete independent wrapper contract | test_aggregate_cte_rejects_modified_outer_projection in both dialects |
| Leaf SQL checks omitted NULL ordering, schema qualifiers and a NULL-predicate RHS | Reject all three altered semantics | test_remaining_ast_semantics_are_independent_of_compiler (six cases) |
| Model context exposed internal IDs behind a granted derived metric | Keep internal formula/component dependencies out of model context | test_derived_model_context_hides_ungranted_dependencies |
| Cancellation test could cancel before query execution | Synchronize cancellation on driver execution instead of timer during compilation | in-flight and pre-cancel Oracle tests |
| v2 seed and existing v1 catalog conflicted for fresh initialization | Separate catalog-v2 default; retain existing v1 catalog/data | Actual CLI initialization with default v2 catalog |

No outstanding must-fix finding was identified for the declared synthetic scope. Safe failed paths
execute no business query. Money stays integer/Decimal; source aggregates precede multi-fact joins
and windows; caps are scoped and short-lived; all new SQL sources and wrappers are independently
checked. No new runtime dependencies or speculative services were added. Deliberate compiler versus
validator duplication is independent security evidence, not a reuse opportunity.

Verdict: Ship. This verdict covers the tested local synthetic baseline only.
Not checked: Actual Gemma/encoder/Oracle, company SSO/VPD, enterprise load, hosted CI, browser,
penetration/egress/license/SBOM approvals and deployment. Lifecycle execution remains unverified.
