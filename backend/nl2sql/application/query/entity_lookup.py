"""Bound exact entity lookups from certified mappings, never user identifiers."""

from decimal import Decimal

from sqlglot import exp

from nl2sql.application.query.physical_sql import oracle_identifiers
from nl2sql.domain.models import Catalog, EntityMapping, Failure, Principal


def entity_query(
    catalog: Catalog, entity: EntityMapping, phrase: str, principal: Principal, dialect: str
) -> tuple[str, dict[str, str | int]]:
    """Limit ambiguous results to two; metadata mappings must belong to the pinned catalog."""
    scopes = principal.regions if entity.scope_claim == "regions" else principal.scopes
    if entity not in catalog.entities or not 1 <= len(phrase) <= 200 or not scopes:
        raise Failure("ENTITY_NOT_FOUND", "No authorized exact entity match was found.")
    parameters: dict[str, str | int] = {"tenant": principal.tenant, "phrase": phrase}
    values: list[exp.Expr] = []
    for i, value in enumerate(sorted(scopes)):
        parameters[f"scope_{i}"] = value
        values.append(exp.Placeholder(this=f"scope_{i}"))
    table = next(table for table in catalog.tables if table.id == entity.table)
    kind = next(column.kind for column in table.columns if column.name == entity.key_column)
    exact: list[exp.Expr] = []
    if kind == "text" or (phrase.isascii() and phrase.isdigit() and len(phrase) <= 38):
        parameters["entity_key"] = int(phrase) if kind == "integer" else phrase
        exact.append(
            exp.EQ(
                this=exp.column(entity.key_column, table=entity.table, quoted=True),
                expression=exp.Placeholder(this="entity_key"),
            )
        )
    exact.extend(
        exp.EQ(
            this=exp.Lower(this=exp.column(key, table=entity.table, quoted=True)),
            expression=exp.Lower(this=exp.Placeholder(this="phrase")),
        )
        for key in entity.label_columns
    )
    if not exact:
        raise Failure("ENTITY_NOT_FOUND", "No authorized exact entity match was found.")
    if not entity.label_columns:
        parameters.pop("phrase")
    query = (
        exp.select(exp.column(entity.key_column, table=entity.table, quoted=True))
        .distinct()
        .from_(exp.to_table(entity.table, quoted=True))
        .where(
            exp.and_(
                exp.EQ(
                    this=exp.column(entity.tenant_column, table=entity.table, quoted=True),
                    expression=exp.Placeholder(this="tenant"),
                ),
                exp.In(
                    this=exp.column(entity.scope_column, table=entity.table, quoted=True),
                    expressions=values,
                ),
                exp.or_(*exact),
            )
        )
        .limit(2)
    )
    if dialect == "oracle":
        query = oracle_identifiers(query, catalog)
    return query.sql(dialect=dialect), parameters


def exact_entity(matches: list[tuple[object, ...]]) -> str:
    """Never leak possible matches across an ambiguity boundary."""
    if len(matches) == 1 and matches[0] and isinstance(matches[0][0], Decimal):
        number = matches[0][0]
        if (
            number.is_finite()
            and number == number.to_integral_value()
            and number.copy_abs() < Decimal("1e38")
        ):
            matches = [(int(number),)]
    if (
        len(matches) != 1
        or not matches[0]
        or not isinstance(matches[0][0], (str, int))
        or isinstance(matches[0][0], bool)
        or len(str(matches[0][0])) > 200
    ):
        raise Failure("ENTITY_AMBIGUOUS", "Use an exact authorized entity identifier.")
    return str(matches[0][0])
