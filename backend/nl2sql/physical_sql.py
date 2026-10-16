"""Quoted Oracle mappings at the SQL boundary; internal plans contain stable approved IDs."""

from sqlglot import exp

from nl2sql.domain import Catalog, Failure


def oracle_identifiers(tree: exp.Expr, catalog: Catalog, reverse: bool = False) -> exp.Expr:
    """Require exact owner/name/alias mappings before independent logical AST validation."""
    result = tree.copy()
    tables = {item.id: item for item in catalog.tables}
    ctes = {item.alias for item in result.find_all(exp.CTE)}
    for node in result.find_all(exp.Table):
        if node.name in ctes and not node.db and not node.catalog and not node.alias:
            continue
        if reverse:
            mapping = next(
                (
                    item
                    for item in catalog.tables
                    if (node.db or None) == item.physical_owner
                    and node.name == (item.physical_name or item.id)
                    and node.alias == (item.id if item.physical_owner or item.physical_name else "")
                ),
                None,
            )
            if mapping is None or node.catalog:
                raise Failure("INVALID_SQL", "Unapproved Oracle physical identifier.")
            node.set("this", exp.to_identifier(mapping.id, quoted=True))
            node.set("db", None)
            node.set("alias", None)
        else:
            mapping = tables.get(node.name)
            if mapping is None or node.db or node.catalog or node.alias:
                raise Failure("INVALID_SQL", "Unapproved internal source identifier.")
            node.set("this", exp.to_identifier(mapping.physical_name or mapping.id, quoted=True))
            if mapping.physical_owner:
                node.set("db", exp.to_identifier(mapping.physical_owner, quoted=True))
            if mapping.physical_owner or mapping.physical_name:
                node.set("alias", exp.TableAlias(this=exp.to_identifier(mapping.id, quoted=True)))
    for node in result.find_all(exp.Column):
        if node.db or node.catalog:
            raise Failure("INVALID_SQL", "Unapproved qualified column identifier.")
        mapping = tables.get(node.table)
        if mapping is None:
            continue
        column = (
            next(
                (
                    item
                    for item in mapping.columns
                    if (item.physical_name or item.name) == node.name
                ),
                None,
            )
            if reverse
            else next((item for item in mapping.columns if item.name == node.name), None)
        )
        if column is None:
            raise Failure("INVALID_SQL", "Unapproved physical column identifier.")
        node.set(
            "this",
            exp.to_identifier(
                column.name if reverse else column.physical_name or column.name, quoted=True
            ),
        )
    return result
