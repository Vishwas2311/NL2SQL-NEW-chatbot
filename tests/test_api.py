"""Contract tests exercise the actual FastAPI boundary without opening the UI."""

import json
import logging
import time

import jwt
import pytest
from fastapi.testclient import TestClient
from nl2sql.api import create_app
from nl2sql.auth import Authenticator
from nl2sql.domain import Failure
from nl2sql.model import MockModel
from pydantic import SecretStr
from test_pipeline import plan_for


def header(credentials, user="analyst"):
    return {"Authorization": "Bearer " + credentials[user]}


def test_all_ews_routes_and_response_keys(settings, credentials):
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json() == {"status": "healthy"}
        assert client.get("/api/v1/health/ready").status_code == 200
        response = client.post(
            "/ews-chatbot/chat",
            headers=header(credentials),
            json={
                "message": "Show total loan exposure by region",
                "session_id": None,
                "user_id": "analyst",
            },
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert {"session_id", "response", "results"} <= result.keys()
        assert result["results"] == [
            {"region": "Demo North", "loan_exposure": "175000.50"},
            {"region": "Demo South", "loan_exposure": "75000.00"},
        ]
        assert "sql_query" not in result
        key = result["session_id"]
        listing = client.get("/ews-chatbot/get_all_sessions", headers=header(credentials)).json()
        assert listing["sessions"][0]["session_id"] == key
        saved = client.get(f"/ews-chatbot/load_session/{key}", headers=header(credentials)).json()
        assert len(saved["messages"]) == 2
        assert saved["messages"][1]["results"] == result["results"]
        assert (
            client.delete(
                f"/ews-chatbot/delete_session/{key}", headers=header(credentials)
            ).status_code
            == 204
        )
        assert (
            client.get(f"/ews-chatbot/load_session/{key}", headers=header(credentials)).status_code
            == 404
        )
        assert response.headers["X-Request-ID"]
        assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/ews-chatbot/chat"),
        ("GET", "/ews-chatbot/get_all_sessions"),
        ("GET", "/ews-chatbot/load_session/unknown"),
        ("DELETE", "/ews-chatbot/delete_session/unknown"),
        ("POST", "/api/v1/speech/transcriptions"),
    ],
)
def test_auth_required(settings, method, path):
    with TestClient(create_app(settings)) as client:
        result = client.request(method, path, json={"message": "Show total loan exposure"})
        assert result.status_code == 401


def test_forged_user_and_cross_user_access(settings, credentials):
    with TestClient(create_app(settings)) as client:
        forged = client.post(
            "/ews-chatbot/chat",
            headers=header(credentials),
            json={"message": "Show total loan exposure", "user_id": "north_analyst"},
        )
        assert forged.status_code == 403
        assert client.get("/ews-chatbot/get_all_sessions", headers=header(credentials)).json() == {
            "sessions": []
        }
        first = client.post(
            "/ews-chatbot/chat",
            headers=header(credentials),
            json={"message": "Show total loan exposure"},
        ).json()
        key = first["session_id"]
        other = header(credentials, "north_analyst")
        for method, path, payload in (
            ("GET", f"/ews-chatbot/load_session/{key}", None),
            ("DELETE", f"/ews-chatbot/delete_session/{key}", None),
            ("POST", "/ews-chatbot/chat", {"message": "and 2025", "session_id": key}),
        ):
            assert client.request(method, path, headers=other, json=payload).status_code == 404
        assert client.get("/ews-chatbot/get_all_sessions", headers=other).json() == {"sessions": []}


def test_mock_model_end_to_end(settings, credentials, resources):
    question = "Summarize outstanding exposure for each region"
    mock = MockModel({question: plan_for(resources).model_dump_json()})
    with TestClient(create_app(settings, mock)) as client:
        response = client.post(
            "/ews-chatbot/chat", headers=header(credentials), json={"message": question}
        )
        assert response.status_code == 200, response.text
        assert response.json()["results"][0]["loan_exposure"] == "175000.50"
        assert response.json()["metadata"]["route"] == "model"
        assert mock.calls == 1
        assert "Other Fiction" not in mock.contexts[0]


@pytest.mark.parametrize(
    "payload",
    [
        "{}",
        "not json",
        '{"sql":"DELETE FROM loans"}',
        '{"catalog_version":"synthetic-v1","principal_id":"root"}',
    ],
)
def test_invalid_model_json_fails_safely(settings, credentials, payload):
    question = "Summarize outstanding exposure for each region"
    with TestClient(create_app(settings, MockModel({question: payload}))) as client:
        result = client.post(
            "/ews-chatbot/chat", headers=header(credentials), json={"message": question}
        )
        assert result.status_code == 503
        assert result.json()["error"]["code"] == "MODEL_INVALID_JSON"
        assert "DELETE" not in result.text


def test_unsupported_clarification_and_speech_disabled(settings, credentials):
    with TestClient(create_app(settings)) as client:
        for text, expected in (
            ("Show exposure", "clarification_required"),
            ("Drop all tables", "unsupported"),
            ("show unicorns", "unsupported"),
        ):
            result = client.post(
                "/ews-chatbot/chat", headers=header(credentials), json={"message": text}
            )
            assert result.status_code == 200
            assert result.json()["status"] == expected
            assert result.json()["results"] == []
        assert (
            client.post("/api/v1/speech/transcriptions", headers=header(credentials)).status_code
            == 501
        )


def test_body_limits_safe_validation_and_request_id(settings, credentials):
    with TestClient(create_app(settings)) as client:
        for payload in (
            {"message": "x", "sql": "secret schema"},
            {"message": ""},
            {"message": "x" * 4001},
        ):
            response = client.post("/ews-chatbot/chat", headers=header(credentials), json=payload)
            assert response.status_code == 422
            assert "secret" not in response.text
        response = client.post(
            "/ews-chatbot/chat", headers=header(credentials), content=b"x" * 33000
        )
        assert response.status_code == 413
        response = client.get("/health", headers={"X-Request-ID": "malicious-log-data"})
        assert response.headers["X-Request-ID"] != "malicious-log-data"


def test_rate_limit(settings, credentials):
    settings = settings.model_copy(update={"requests_per_minute": 1})
    with TestClient(create_app(settings)) as client:
        assert (
            client.get("/ews-chatbot/get_all_sessions", headers=header(credentials)).status_code
            == 200
        )
        assert (
            client.get("/ews-chatbot/get_all_sessions", headers=header(credentials)).status_code
            == 429
        )


@pytest.mark.parametrize(
    "claim_update", [{"exp": 0}, {"iss": "attacker"}, {"aud": "elsewhere"}, {"sub": "unknown"}]
)
def test_jwt_claim_validation(settings, claim_update):
    secret = "test-only-secret-with-at-least-32-characters"
    auth = Authenticator(settings.model_copy(update={"jwt_secret": SecretStr(secret)}))
    claims = {
        "sub": "analyst",
        "iss": "ews-local",
        "aud": "ews-backend",
        "iat": int(time.time()),
        "exp": int(time.time()) + 60,
        **claim_update,
    }
    with pytest.raises(Failure):
        auth.authenticate("Bearer " + jwt.encode(claims, secret, algorithm="HS256"))


def test_jwt_signature_and_server_side_grants(settings):
    secret = "test-only-secret-with-at-least-32-characters"
    auth = Authenticator(settings.model_copy(update={"jwt_secret": SecretStr(secret)}))
    claims = {
        "sub": "north_analyst",
        "iss": "ews-local",
        "aud": "ews-backend",
        "iat": int(time.time()),
        "exp": int(time.time()) + 60,
        "regions": ["south"],
    }
    assert auth.authenticate("Bearer " + jwt.encode(claims, secret, algorithm="HS256")).regions == (
        "north",
    )
    with pytest.raises(Failure):
        auth.authenticate(
            "Bearer "
            + jwt.encode(claims, "wrong-secret-that-is-longer-than-32-bytes", algorithm="HS256")
        )


def test_pipeline_logs_correlate_without_private_content(settings, credentials, caplog):
    with caplog.at_level(logging.INFO, logger="nl2sql"), TestClient(create_app(settings)) as client:
        response = client.post(
            "/ews-chatbot/chat",
            headers=header(credentials),
            json={"message": "Show total loan exposure"},
        )
    events = [json.loads(record.message) for record in caplog.records if record.name == "nl2sql"]
    pipeline = next(event for event in events if event["event"] == "pipeline")
    assert pipeline["request_id"] == response.headers["X-Request-ID"]
    assert "Show total" not in json.dumps(events)
    assert credentials["analyst"] not in json.dumps(events)
