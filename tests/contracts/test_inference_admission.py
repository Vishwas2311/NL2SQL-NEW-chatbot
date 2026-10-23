"""Slow planning must leave bounded capacity for certified reporting."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import httpx
import pytest
from fastapi.testclient import TestClient
from nl2sql.application.ports import ModelResult
from nl2sql.bootstrap.factory import create_app
from nl2sql.domain.fingerprints import digest
from nl2sql.domain.models import Failure
from nl2sql.infrastructure.inference.model import PrivateHTTPModel
from nl2sql.settings import TokenGrant

from tests.contracts.test_providers_failures import model_settings
from tests.integration.test_pipeline import plan_for


@pytest.mark.parametrize("path", ["/ews-chatbot/chat", "/api/v1/chat"])
def test_slow_inference_leaves_template_capacity_and_preserves_user_limit(
    settings, resources, path
):
    entered, release = Event(), Event()
    plan = plan_for(resources)

    class SlowModel:
        def plan(self, _question, _context, _deadline, _cancelled=None):
            entered.set()
            assert release.wait(10), "Synthetic inference was not released"
            return ModelResult(plan, 1, 0)

        def close(self):
            release.set()

    users = tuple(
        settings.principals[0].model_copy(update={"id": f"gate-user-{i}"}) for i in range(2)
    )
    tokens = ("fictional-inference-user-a", "fictional-inference-user-b")
    configuration = settings.model_copy(
        update={
            "principals": users,
            "tokens": tuple(
                TokenGrant(sha256=digest(token), principal_id=user.id)
                for token, user in zip(tokens, users, strict=True)
            ),
            "max_concurrent_chats": 3,
            "max_concurrent_inferences": 1,
        }
    )
    first, second = ({"Authorization": "Bearer " + token} for token in tokens)
    with TestClient(create_app(configuration, SlowModel())) as client:
        with ThreadPoolExecutor(1) as pool:
            pending = pool.submit(
                client.post,
                path,
                headers=first,
                json={"message": "Give me an update on total loan exposure"},
            )
            try:
                assert entered.wait(5)
                response = client.post(
                    path, headers=second, json={"message": "Show total loan exposure by region"}
                )
                assert response.status_code == 200
                session = response.json()["session_id"]
                followup = client.post(
                    path, headers=second, json={"message": "and 2025", "session_id": session}
                )
                assert followup.status_code == 200
                busy = client.post(
                    path,
                    headers=second,
                    json={"message": "Give me an update on total loan exposure"},
                )
                assert (
                    busy.status_code == 429 and busy.json()["error"]["code"] == "INFERENCE_CAPACITY"
                )
                assert busy.headers["Retry-After"] == "1"
                owned = client.post(
                    path, headers=first, json={"message": "Show total loan exposure by region"}
                )
                assert (
                    owned.status_code == 429 and owned.json()["error"]["code"] == "CHAT_IN_PROGRESS"
                )
            finally:
                release.set()
            assert pending.result(timeout=5).status_code == 200
        recovered = client.post(
            path, headers=second, json={"message": "Give me an update on total loan exposure"}
        )
        assert recovered.status_code == 200


@pytest.mark.parametrize("mode", ["json_schema", "json_object", "text_json"])
def test_chat_http_payload_sends_decision_schema_once(settings, resources, mode):
    plan = plan_for(resources)
    payloads = []

    def respond(request):
        body = json.loads(request.content)
        payloads.append(body)
        context = json.loads(json.loads(body["messages"][1]["content"])["metadata"])
        assert ("schema" in context) == (mode != "json_schema")
        if mode == "json_schema":
            assert body["response_format"]["json_schema"]["schema"]["properties"]["outcome"]
        elif mode == "json_object":
            assert body["response_format"] == {"type": "json_object"}
        else:
            assert "response_format" not in body
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

    configuration = model_settings(settings, model_output_mode=mode)
    resources.service.settings = configuration
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        resources.service.model.provider = PrivateHTTPModel(configuration, client)
        answer = resources.service.chat(
            "Give me an update on total loan exposure",
            None,
            resources.auth.principals["analyst"],
            None,
            {},
        )
    assert answer.status == "completed" and len(payloads) == 1


@pytest.mark.parametrize("code", ["MODEL_TIMEOUT", "MODEL_INVALID_JSON"])
def test_inference_failure_releases_slot(resources, code):
    original = resources.service.model.provider

    class BrokenModel:
        def plan(self, *_args):
            raise Failure(code, "Synthetic model failure.", "unavailable")

        def close(self):
            pass

    resources.service.model.provider = BrokenModel()
    user = resources.auth.principals["analyst"]
    with pytest.raises(Failure) as error:
        resources.service.chat("Give me an update on total loan exposure", None, user, None, {})
    assert error.value.code == code
    resources.service.model.provider = original
    original.plans["Give me an update on total loan exposure"] = plan_for(
        resources
    ).model_dump_json()
    assert (
        resources.service.chat(
            "Give me an update on total loan exposure", None, user, None, {}
        ).status
        == "completed"
    )
