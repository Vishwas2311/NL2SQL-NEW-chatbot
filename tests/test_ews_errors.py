"""The real JS API wrapper reads errorBody.detail || errorBody.message."""

import pytest
from fastapi.testclient import TestClient
from nl2sql.api import create_app


@pytest.mark.parametrize(
    "path,body",
    [
        ("/ews-chatbot/chat", {"message": "Show total loan exposure"}),
        ("/ews-chatbot/load_session/missing", None),
        ("/api/v1/speech/transcriptions", None),
    ],
)
def test_legacy_auth_errors_have_displayable_text(settings, path, body):
    with TestClient(create_app(settings)) as client:
        response = client.request("POST" if body or "speech" in path else "GET", path, json=body)
    assert response.status_code == 401
    result = response.json()
    assert isinstance(result["detail"], str)
    assert result["detail"] == result["message"] == result["error"]["message"]
    assert result["results"] == []


def test_internal_errors_keep_the_typed_contract(settings):
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/v1/chat", json={"message": "x"})
    assert response.status_code == 401
    assert set(response.json()) == {"error"}


def test_legacy_validation_identity_session_and_body_errors(settings, credentials):
    headers = {"Authorization": "Bearer " + credentials["analyst"]}
    with TestClient(create_app(settings)) as client:
        responses = [
            client.post("/ews-chatbot/chat", headers=headers, json={"message": ""}),
            client.post(
                "/ews-chatbot/chat", headers=headers, json={"message": "x", "user_id": "other"}
            ),
            client.get("/ews-chatbot/load_session/missing", headers=headers),
            client.post("/ews-chatbot/chat", content=b"x" * 33000),
            client.post("/api/v1/speech/transcriptions", headers=headers),
        ]
    assert [item.status_code for item in responses] == [422, 403, 404, 413, 501]
    assert all(isinstance(item.json()["detail"], str) for item in responses)
