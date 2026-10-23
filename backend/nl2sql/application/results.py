"""Exact result formatting is independent of routing, inference and persistence."""

from decimal import Decimal, localcontext

from nl2sql.domain.models import Catalog, QueryPlan, Row, money_text


def format_rows(rows: tuple[Row, ...], plan: QueryPlan, catalog: Catalog) -> tuple[Row, ...]:
    """Format certified scale/units using Decimal, without binary floating-point money."""
    with localcontext() as context:
        context.prec = 80
        return decimal_rows(rows, plan, catalog)


def decimal_rows(rows: tuple[Row, ...], plan: QueryPlan, catalog: Catalog) -> tuple[Row, ...]:
    """Apply exact aggregates and remove internal numerator/count output columns."""
    metrics = {metric.id: metric for metric in catalog.metrics}
    result: list[Row] = []
    for row in rows:
        record = dict(row)
        for key in plan.metrics:
            metric = metrics[key]
            value = row[key]
            if metric.expression is not None and metric.expression.kind == "ratio":
                denominator = record.pop(key + "_d")
                record[key] = (
                    format(
                        Decimal(str(value)) * 100 / Decimal(str(denominator)),
                        f".{metric.decimal_places}f",
                    )
                    if value is not None and denominator
                    else None
                )
            elif metric.aggregate == "avg":
                count = row[key + "_n"]
                del record[key + "_n"]
                record[key] = (
                    format(
                        Decimal(str(value)) / Decimal(str(count)) / metric.scale,
                        f".{metric.decimal_places}f",
                    )
                    if value is not None and count
                    else None
                )
            elif metric.unit not in {"count", "percent"} and value is not None:
                record[key] = money_text(str(value), metric.scale, metric.decimal_places)
        result.append(record)
    return tuple(result)
