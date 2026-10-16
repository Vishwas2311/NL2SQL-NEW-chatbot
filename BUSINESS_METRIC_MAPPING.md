# Business mappings

Certified metadata declares metric ID, aliases, definition, source table/column, aggregate, temporal
kind, currency/unit, divisor scale and output decimal places. Discovery cannot invent these meanings.

Loan exposure uses SUM(amount_minor)/100; loan count uses COUNT(loan_id); average exposure returns
exact sum/count before Decimal formatting. Account/payment measures retain their own native grains.
Difference/percentage expressions reference compatible approved primitive sums. All records are fictional.

Oracle Column.kind=decimal maps known NUMBER precision/scale; integer requires integral storage.
A major-unit currency declares scale=1; minor-unit currency declares its divisor. decimal_places
governs output precision. NUMBER(38,6), USD major units and six-place output are tested through an
injected driver, including a 38-digit value. Money never uses a binary float.

Changed aliases, sources, formulas, units, scales, views, time rules or grants need signed review.
Metadata text and model output cannot confer permissions. New metrics need explicit grants before
retrieval or execution. No corporate business mapping has been approved.
