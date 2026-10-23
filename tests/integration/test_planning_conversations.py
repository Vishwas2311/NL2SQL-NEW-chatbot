"""SLM clarification and follow-ups remain bounded, owned and currently authorized."""

import json

import pytest
from nl2sql.domain.models import Failure

from tests.integration.test_pipeline import plan_for


@pytest.mark.parametrize(
    "question",
    [
        "Give me an update on total loan exposure",
        "Update me on total loan exposure",
        "Update us on total loan exposure",
        "Drop in total loan exposure this month",
    ],
)
def test_read_only_update_phrase_reaches_typed_planning(resources, question):
    resources.model.plans[question] = plan_for(resources).model_dump_json()
    answer = resources.service.chat(question, None, resources.auth.principals["analyst"], None, {})
    assert answer.status == "completed" and resources.model.calls == 1


@pytest.mark.parametrize(
    "question", ["Delete all loans", "Drop all tables", "UPDATE loans SET x=1"]
)
def test_explicit_write_commands_execute_nothing(resources, question):
    answer = resources.service.chat(question, None, resources.auth.principals["analyst"], None, {})
    assert answer.status == "unsupported"
    assert resources.model.calls == 0 and resources.database.execute_count == 0


def test_model_clarification_executes_nothing_and_resumes(resources):
    user = resources.auth.principals["analyst"]
    question = "Which loan exposure report is appropriate?"
    resources.model.plans[question] = json.dumps(
        {
            "outcome": {
                "kind": "clarification",
                "reason": "metric",
                "metric_ids": ["loan_exposure"],
            }
        }
    )
    answer = resources.service.chat(question, None, user, None, {})
    assert answer.status == "clarification_required" and resources.database.execute_count == 0
    resources.model.plans["Use loan exposure"] = plan_for(resources).model_dump_json()
    resumed = resources.service.chat("Use loan exposure", answer.session_id, user, None, {})
    assert resumed.status == "completed"
    context = json.loads(resources.model.contexts[-1])
    assert context["pending_question"]["question"] == question
    assert resources.sessions.state(answer.session_id, user.id).pending is None


def test_flexible_followup_receives_only_current_typed_context(resources):
    user = resources.auth.principals["analyst"]
    first = resources.service.chat("Show total loan exposure by region", None, user, None, {})
    question = "Break that down by customer"
    resources.model.plans[question] = plan_for(
        resources, dimensions=("customer_id",)
    ).model_dump_json()
    answer = resources.service.chat(question, first.session_id, user, None, {})
    assert answer.status == "completed"
    context = json.loads(resources.model.contexts[-1])
    assert context["previous_plan"]["metrics"] == ["loan_exposure"]
    assert "messages" not in context and "results" not in context
    reduced = user.model_copy(update={"metrics": ("account_count",)})
    before = resources.model.calls
    denied_context = resources.service.chat(question, first.session_id, reduced, None, {})
    assert denied_context.status == "clarification_required" and resources.model.calls == before


def test_clarification_cannot_offer_unretrieved_or_ungranted_metrics(resources):
    user = resources.auth.principals["analyst"].model_copy(update={"metrics": ("loan_exposure",)})
    question = "Please explain the loan exposure reporting choice"
    resources.model.plans[question] = json.dumps(
        {
            "outcome": {
                "kind": "clarification",
                "reason": "metric",
                "metric_ids": ["account_count"],
            }
        }
    )
    with pytest.raises(Failure) as error:
        resources.service.chat(question, None, user, None, {})
    assert error.value.code == "UNGROUNDED_PLAN" and resources.database.execute_count == 0


def test_unusable_previous_plan_does_not_block_a_new_complete_question(resources, monkeypatch):
    user = resources.auth.principals["analyst"]
    first = resources.service.chat("Show total loan exposure by region", None, user, None, {})
    original = resources.service.compiler.validator.validate

    def validate(plan, principal):
        if plan.metrics == ("loan_exposure",):
            raise Failure("VIEW_STALE", "Previous report is unavailable.", "conflict")
        return original(plan, principal)

    monkeypatch.setattr(resources.service.compiler.validator, "validate", validate)
    answer = resources.service.chat(
        "Show account count by region", first.session_id, user, None, {}
    )
    assert answer.status == "completed"
