"""The runtime tokenizer must count the complete request before generation."""

import json
import time

import httpx
import pytest
from nl2sql.domain.models import Failure
from nl2sql.domain.planning import ClarificationRequest
from nl2sql.infrastructure.inference.model import PrivateHTTPModel

from tests.contracts.test_providers_failures import model_settings
from tests.integration.test_pipeline import plan_for


@pytest.mark.parametrize("input_tokens,allowed", [(700, True), (900, False)])
def test_complete_token_budget_reserves_output(settings, resources, input_tokens, allowed):
    calls = []
    plan = plan_for(resources)

    def respond(request):
        calls.append(request.url.path)
        body = json.loads(request.content)
        assert body["messages"][1]["content"]
        assert body["response_format"]["json_schema"]["schema"]
        if request.url.path.endswith("input_tokens"):
            return httpx.Response(200, json={"input_tokens": input_tokens})
        return httpx.Response(
            200,
            json={
                "id": "synthetic",
                "object": "chat.completion",
                "created": 1,
                "model": "gemma-4-12b",
                "choices": [{"message": {"role": "assistant", "content": plan.model_dump_json()}}],
            },
        )

    configuration = model_settings(
        settings,
        model_token_count_endpoint="http://127.0.0.1:9999/v1/chat/completions/input_tokens",
        model_context_tokens=2048,
        model_token_safety_margin=128,
    )
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        provider = PrivateHTTPModel(configuration, client)
        if allowed:
            assert provider.plan("question", "metadata", time.time() + 5).plan == plan
            assert calls == ["/v1/chat/completions/input_tokens", "/v1/chat/completions"]
        else:
            with pytest.raises(Failure) as error:
                provider.plan("question", "metadata", time.time() + 5)
            assert error.value.code == "MODEL_CONTEXT_BUDGET"
            assert calls == ["/v1/chat/completions/input_tokens"]


def test_restricted_inference_requires_tokenizer_before_generation(settings):
    configuration = model_settings(settings, data_classification="restricted")
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: pytest.fail("Unexpected network"))
    ) as client:
        provider = PrivateHTTPModel(configuration, client)
        with pytest.raises(Failure) as error:
            provider.plan("question", "metadata", time.time() + 5)
        assert error.value.code == "MODEL_TOKENIZER_REQUIRED"


@pytest.mark.parametrize("count", [-1, True, "700", None])
def test_invalid_token_count_cannot_reach_generation(settings, count):
    paths = []

    def respond(request):
        paths.append(request.url.path)
        return httpx.Response(200, json={"input_tokens": count})

    configuration = model_settings(
        settings, model_token_count_endpoint="http://127.0.0.1:9999/count"
    )
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(Failure) as error:
            PrivateHTTPModel(configuration, client).plan("question", "metadata", time.time() + 5)
    assert error.value.code == "MODEL_TOKENIZER_INVALID" and paths == ["/count"]


def test_tokenizer_cannot_send_metadata_to_another_origin(settings):
    configuration = model_settings(settings, model_token_count_endpoint="http://127.0.0.2/count")
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: pytest.fail("Cross-origin request"))
    ) as client:
        with pytest.raises(Failure) as error:
            PrivateHTTPModel(configuration, client).plan("question", "metadata", time.time() + 5)
    assert error.value.code == "MODEL_TOKENIZER_CONFIGURATION"


def test_over_budget_context_removes_only_optional_records(settings, resources):
    plan = plan_for(resources)
    counted = []

    def respond(request):
        body = json.loads(request.content)
        context = json.loads(json.loads(body["messages"][1]["content"])["metadata"])
        assert context["metrics"] == [{"id": "loan_exposure"}]
        if request.url.path == "/count":
            counted.append(context)
            return httpx.Response(
                200, json={"input_tokens": 900 if context["schema_records"] else 700}
            )
        assert context["schema_records"] == [] and context["truncated"]
        return httpx.Response(
            200,
            json={
                "id": "test",
                "object": "chat.completion",
                "created": 1,
                "model": "gemma-4-12b",
                "choices": [{"message": {"role": "assistant", "content": plan.model_dump_json()}}],
            },
        )

    configuration = model_settings(
        settings,
        model_token_count_endpoint="http://127.0.0.1:9999/count",
        model_context_tokens=2048,
    )
    context = json.dumps(
        {"metrics": [{"id": "loan_exposure"}], "schema_records": [{"id": "optional"}]}
    )
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = PrivateHTTPModel(configuration, client).plan("question", context, time.time() + 5)
    assert result.input_tokens == 700 and len(counted) == 2


def test_http_planning_accepts_typed_clarification_envelope(settings):
    def respond(request):
        body = json.loads(request.content)
        assert "outcome" in body["response_format"]["json_schema"]["schema"]["properties"]
        return httpx.Response(
            200,
            json={
                "id": "synthetic",
                "object": "chat.completion",
                "created": 1,
                "model": "gemma-4-12b",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "outcome": {
                                        "kind": "clarification",
                                        "reason": "period",
                                        "metric_ids": [],
                                    }
                                }
                            ),
                        }
                    }
                ],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = PrivateHTTPModel(model_settings(settings), client).plan(
            "question", "{}", time.time() + 5
        )
    assert isinstance(result.plan, ClarificationRequest) and result.plan.reason == "period"
