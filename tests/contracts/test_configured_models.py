"""Provider flexibility must not weaken data, identity or typed-plan boundaries."""

import json
import time

import httpx
import pytest
from nl2sql.domain.models import Failure
from nl2sql.infrastructure.inference.model import build_model
from nl2sql.settings import Settings

DECISION = {"outcome": {"kind": "clarification", "reason": "metric", "metric_ids": []}}


def configuration(**changes):
    return Settings.model_validate(
        {
            "model_mode": "configured_http",
            "model_endpoint": "https://approved.example.invalid/openai/v1/chat/completions",
            "approved_model_hosts": ("approved.example.invalid",),
            "model_name": "office-deployment",
            "model_network": "approved_https",
            "model_restricted_data_authorized": True,
            "model_token_budget": "provider",
            **changes,
        }
    )


def reply(api="chat_completions", **changes):
    if api == "responses":
        return {
            "id": "synthetic",
            "object": "response",
            "model": "office-deployment",
            "status": "completed",
            "output": [
                {"type": "reasoning", "summary": []},
                {
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "output_text", "text": json.dumps(DECISION)}],
                },
            ],
            **changes,
        }
    return {
        "id": "synthetic",
        "object": "chat.completion",
        "created": 1,
        "model": "office-deployment",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": json.dumps(DECISION),
                },
            }
        ],
        **changes,
    }


def invoke(monkeypatch, settings, response, inspect=lambda _: None):
    calls = []

    def respond(request):
        calls.append(request)
        inspect(request)
        return response

    client = httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr("nl2sql.infrastructure.inference.model.private_client", lambda _: client)
    provider = build_model(settings)
    try:
        result = provider.plan(
            "synthetic question", '{"classification":"restricted"}', time.time() + 5
        )
        assert result.plan.reason == "metric"
        return calls
    finally:
        provider.close()
        assert client.is_closed


@pytest.mark.parametrize("api", ["chat_completions", "responses"])
@pytest.mark.parametrize(
    "auth,header", [("api_key", "api-key"), ("bearer", "authorization"), ("none", None)]
)
def test_approved_azure_and_compatible_protocols(monkeypatch, api, auth, header):
    settings = configuration(
        model_api=api,
        model_auth=auth,
        model_key="synthetic-key",
        model_temperature=None,
        model_reasoning_effort="low",
        model_token_parameter="max_completion_tokens",
    )
    settings = (
        settings.model_copy(
            update={"model_endpoint": settings.model_endpoint.rsplit("/", 2)[0] + "/responses"}
        )
        if api == "responses"
        else settings
    )

    def inspect(request):
        body = json.loads(request.content)
        assert "temperature" not in body and "tools" not in body
        if header:
            assert "synthetic-key" in request.headers[header]
        else:
            assert "api-key" not in request.headers and "authorization" not in request.headers
        if api == "responses":
            assert body["max_output_tokens"] == settings.model_max_tokens
            assert body["store"] is False and body["truncation"] == "disabled"
            assert body["text"]["format"]["type"] == "json_schema"
            assert body["reasoning"] == {"effort": "low"}
        else:
            assert body["max_completion_tokens"] == settings.model_max_tokens
            assert "max_tokens" not in body and body["reasoning_effort"] == "low"
            schema = body["response_format"]["json_schema"]["schema"]
            assert set(schema["required"]) == set(schema["properties"])
            for definition in schema["$defs"].values():
                if definition.get("type") == "object":
                    assert set(definition["required"]) == set(definition["properties"])
                    assert definition["additionalProperties"] is False

    assert len(invoke(monkeypatch, settings, httpx.Response(200, json=reply(api)), inspect)) == 1


def test_azure_api_version_and_explicit_returned_identity(monkeypatch):
    settings = configuration(
        model_auth="api_key",
        model_key="synthetic-key",
        model_api_version="2024-10-21",
        model_response_ids=("gpt-version",),
    )

    def inspect(request):
        assert request.url.params["api-version"] == "2024-10-21"

    invoke(monkeypatch, settings, httpx.Response(200, json=reply(model="gpt-version")), inspect)


@pytest.mark.parametrize(
    "changes",
    [
        {"model_restricted_data_authorized": False},
        {"model_endpoint": "http://approved.example.invalid/chat"},
        {"approved_model_hosts": ()},
        {"model_endpoint": "https://user:password@approved.example.invalid/chat"},
        {"model_endpoint": "https://approved.example.invalid/chat?api-key=secret"},
    ],
)
def test_invalid_or_unapproved_configuration_fails_before_network(monkeypatch, changes):
    monkeypatch.setattr("httpx.Client.send", lambda *_: pytest.fail("No network permitted"))
    values = configuration().model_dump()
    values.update(changes)
    with pytest.raises(ValueError):
        build_model(Settings.model_validate(values))


@pytest.mark.parametrize("api", ["chat_completions", "responses"])
@pytest.mark.parametrize(
    "change,code",
    [
        ("identity", "MODEL_IDENTITY"),
        ("tools", "MODEL_INVALID_JSON"),
        ("truncated", "MODEL_INVALID_JSON"),
    ],
)
def test_untrusted_provider_output_is_denied(monkeypatch, api, change, code):
    body = reply(api)
    if change == "identity":
        body["model"] = "unapproved-model"
    elif api == "responses":
        if change == "tools":
            body["output"].append({"type": "function_call", "name": "database"})
        else:
            body["status"] = "incomplete"
    elif change == "tools":
        body["choices"][0]["message"]["tool_calls"] = [{"name": "database"}]
    else:
        body["choices"][0]["finish_reason"] = "length"
    with pytest.raises(Failure) as error:
        invoke(monkeypatch, configuration(model_api=api), httpx.Response(200, json=body))
    assert error.value.code == code


def test_context_error_is_safe_and_not_retried(monkeypatch):
    with pytest.raises(Failure) as error:
        invoke(
            monkeypatch,
            configuration(model_retries=1),
            httpx.Response(
                400,
                json={
                    "error": {
                        "code": "context_length_exceeded",
                        "message": "private prompt details",
                    }
                },
            ),
        )
    assert error.value.code == "MODEL_CONTEXT_BUDGET"
    assert "private prompt" not in error.value.message


@pytest.mark.parametrize("api", ["chat_completions", "responses"])
@pytest.mark.parametrize("output_mode", ["json_object", "text_json"])
def test_json_modes_are_configurable(monkeypatch, api, output_mode):
    def inspect(request):
        payload = json.loads(request.content)
        key = "text" if api == "responses" else "response_format"
        assert (key in payload) == (output_mode == "json_object")

    invoke(
        monkeypatch,
        configuration(model_api=api, model_output_mode=output_mode),
        httpx.Response(200, json=reply(api)),
        inspect,
    )


@pytest.mark.parametrize("api", ["chat_completions", "responses"])
def test_optional_runtime_counter_counts_final_protocol_payload(monkeypatch, api):
    calls = []

    def respond(request):
        calls.append(request)
        if request.url.path == "/count":
            payload = json.loads(request.content)
            assert ("input" in payload) == (api == "responses")
            return httpx.Response(200, json={"input_tokens": 300})
        return httpx.Response(200, json=reply(api))

    client = httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr("nl2sql.infrastructure.inference.model.private_client", lambda _: client)
    provider = build_model(
        configuration(
            model_api=api,
            model_token_budget="runtime",
            model_token_count_endpoint="https://approved.example.invalid/count",
        )
    )
    try:
        result = provider.plan("synthetic", '{"classification":"restricted"}', time.time() + 5)
        assert result.input_tokens == 300 and len(calls) == 2
    finally:
        provider.close()


@pytest.mark.parametrize(
    "context",
    ["{}", '{"classification":[]}', '{"classification":{}}', '{"classification":"restricted"}'],
)
def test_actual_context_cannot_bypass_endpoint_authorization(monkeypatch, context):
    client = httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("Egress blocked")))
    monkeypatch.setattr("nl2sql.infrastructure.inference.model.private_client", lambda _: client)
    provider = build_model(
        configuration(data_classification="synthetic", model_restricted_data_authorized=False)
    )
    try:
        with pytest.raises(Failure) as error:
            provider.plan("synthetic", context, time.time() + 5)
        assert error.value.code == "EGRESS_DENIED"
    finally:
        provider.close()


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "MODEL_AUTHENTICATION"),
        (403, "MODEL_AUTHENTICATION"),
        (404, "MODEL_REQUEST_REJECTED"),
        (422, "MODEL_REQUEST_REJECTED"),
    ],
)
def test_safe_provider_diagnostics(monkeypatch, status, code):
    with pytest.raises(Failure) as error:
        invoke(monkeypatch, configuration(), httpx.Response(status, content=b"private body"))
    assert error.value.code == code and "private body" not in error.value.message


@pytest.mark.parametrize("api", ["chat_completions", "responses"])
def test_provider_usage_cannot_exceed_configured_budget(monkeypatch, api):
    usage = (
        {"input_tokens": 8000, "output_tokens": 10, "total_tokens": 8010}
        if api == "responses"
        else {"prompt_tokens": 8000, "completion_tokens": 10, "total_tokens": 8010}
    )
    with pytest.raises(Failure) as error:
        invoke(
            monkeypatch,
            configuration(model_api=api),
            httpx.Response(200, json=reply(api, usage=usage)),
        )
    assert error.value.code == "MODEL_CONTEXT_BUDGET"


def test_temperature_can_be_omitted_in_private_environment(tmp_path):
    from nl2sql.settings import load_settings

    environment = tmp_path / "synthetic.env"
    environment.write_text("NL2SQL_MODEL_TEMPERATURE=null\n")
    assert load_settings(env_file=environment).model_temperature is None


@pytest.mark.parametrize("api", ["chat_completions", "responses"])
def test_wire_schema_is_portable_but_returned_decision_is_fully_validated(monkeypatch, api):
    forbidden = {
        "default",
        "const",
        "format",
        "pattern",
        "minLength",
        "maxLength",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minItems",
        "maxItems",
    }

    def check(value):
        if isinstance(value, dict):
            assert not forbidden.intersection(value)
            for item in value.values():
                check(item)
        elif isinstance(value, list):
            for item in value:
                check(item)

    def inspect(request):
        payload = json.loads(request.content)
        check(
            payload["text"]["format"]["schema"]
            if api == "responses"
            else payload["response_format"]["json_schema"]["schema"]
        )

    body = reply(api)
    invalid = json.dumps(
        {"outcome": {"kind": "clarification", "reason": "metric", "metric_ids": ["invalid id!"]}}
    )
    if api == "responses":
        body["output"][1]["content"][0]["text"] = invalid
    else:
        body["choices"][0]["message"]["content"] = invalid
    with pytest.raises(Failure) as error:
        invoke(monkeypatch, configuration(model_api=api), httpx.Response(200, json=body), inspect)
    assert error.value.code == "MODEL_INVALID_JSON"
