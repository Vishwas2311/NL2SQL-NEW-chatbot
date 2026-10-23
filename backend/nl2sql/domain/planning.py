"""Model decisions contain approved IDs or a bounded clarification, never tools or SQL."""

import json
from typing import Literal

from pydantic import Field, TypeAdapter

from nl2sql.domain.models import FrozenModel, Identifier, QueryPlan


class ClarificationRequest(FrozenModel):
    """The application supplies the wording and verifies every suggested metric."""

    kind: Literal["clarification"]
    reason: Literal["metric", "period", "dimension", "filter", "entity"]
    metric_ids: tuple[Identifier, ...] = Field(default=(), max_length=5)


class PlanningDecision(FrozenModel):
    """One object-shaped structured response, suitable for constrained model runtimes."""

    outcome: QueryPlan | ClarificationRequest


class PendingQuestion(FrozenModel):
    """Only the unresolved bounded question survives; it never conveys authorization."""

    question: str = Field(min_length=1, max_length=4000)
    catalog_version: str
    metric_ids: tuple[Identifier, ...] = Field(max_length=50)


def parse_decision(payload: str) -> QueryPlan | ClarificationRequest:
    """Read the new envelope and existing direct-plan provider contracts."""
    value = json.loads(payload)
    if isinstance(value, dict) and "outcome" in value:
        return PlanningDecision.model_validate(value).outcome
    return TypeAdapter(QueryPlan | ClarificationRequest).validate_python(value)
