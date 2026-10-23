"""Cheap exact routing; flexible questions remain typed model decisions."""

import re
from datetime import date

from nl2sql.application.text import normalize
from nl2sql.domain.models import Catalog, Failure, Period, QueryPlan, Sort
from nl2sql.domain.sessions import SessionState


def certified_template(question: str, catalog: Catalog) -> QueryPlan | None:
    """Exact full-sentence match; similar wording must use structured planning."""
    match = next(
        (item for item in catalog.templates if normalize(item.question) == normalize(question)),
        None,
    )
    if match is not None:
        return match.plan
    return None


def followup(question: str, state: SessionState, catalog: Catalog) -> QueryPlan | None:
    """Transform only recognized slots; all resulting plans are validated again."""
    text = normalize(question)
    commands = {
        "what about last year",
        "now group it by region",
        "give the top five",
        "compare those results",
        "show the same for another branch",
    }
    match = re.fullmatch(
        r"(?:and |what about |make that )(\d{4}(?:-\d{2}-\d{2})?)\??",
        question.strip().casefold(),
    )
    if match is None and text not in commands and not text.startswith("now group it by "):
        return None
    previous = state.last_plan
    if previous is None or previous.catalog_version != catalog.version:
        raise Failure("CLARIFICATION", "Ask a complete question with a reporting date first.")
    if text in {"compare those results", "show the same for another branch"}:
        raise Failure("CLARIFICATION", "Specify the comparison periods or the exact branch.")
    if text.startswith("now group it by "):
        field = text.removeprefix("now group it by ")
        dimension = next(
            (
                item.id
                for item in catalog.dimensions
                if normalize(item.id.replace("_", " ")) == field
            ),
            None,
        )
        if dimension is None:
            raise Failure("CLARIFICATION", "Specify a certified grouping dimension.")
        return previous.model_copy(update={"dimensions": (dimension,)})
    if text == "give the top five":
        if len(previous.metrics) != 1:
            raise Failure("CLARIFICATION", "Specify which metric determines the top five.")
        return previous.model_copy(
            update={"sort": (Sort(field=previous.metrics[0], direction="desc"),), "limit": 5}
        )
    if not isinstance(previous.period, Period):
        raise Failure("CLARIFICATION", "Ask a complete question with a reporting date first.")
    if text == "what about last year":
        try:
            return previous.model_copy(
                update={
                    "period": Period(
                        as_of=previous.period.as_of.replace(year=previous.period.as_of.year - 1)
                    )
                }
            )
        except ValueError as error:
            raise Failure("CLARIFICATION", "Specify a valid reporting date.") from error
    assert match is not None
    value = match[1]
    try:
        as_of = (
            date.fromisoformat(value)
            if len(value) > 4
            else previous.period.as_of.replace(year=int(value))
        )
    except ValueError as error:
        raise Failure("CLARIFICATION", "Use a valid ISO reporting date.") from error
    return previous.model_copy(update={"period": Period(as_of=as_of)})
