"""Derive bind types from approved AST column mappings, never from model metadata."""

from typing import Literal

from sqlglot import exp

from nl2sql.domain.models import Bind, Catalog


def infer_bind_types(
    tree: exp.Expr, binds: dict[str, Bind], catalog: Catalog
) -> tuple[tuple[str, Literal["text", "integer", "decimal", "date"]], ...]:
    """Oracle receives native DATE binds while SQLite retains ISO date storage."""
    special = {
        (table.id, field.name): field.kind
        for table in catalog.tables
        for field in table.columns
        if field.kind in {"date", "decimal"}
    }
    kinds: dict[str, Literal["text", "integer", "decimal", "date"]] = {
        name: "integer" if isinstance(value, int) else "text" for name, value in binds.items()
    }
    for placeholder in tree.find_all(exp.Placeholder):
        parent = placeholder.parent
        if parent is not None and isinstance(parent.this, exp.Expr):
            for column in parent.this.find_all(exp.Column):
                kind = special.get((column.table, column.name))
                if kind == "date":
                    kinds[placeholder.name] = "date"
                elif kind == "decimal":
                    kinds[placeholder.name] = "decimal"
    return tuple(sorted(kinds.items()))
