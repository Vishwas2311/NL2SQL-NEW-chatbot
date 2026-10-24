"""Real loopback HTTP and the complete API pipeline, with synthetic data only."""

import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient
from nl2sql.bootstrap.factory import create_app
from nl2sql.cli import main as cli
from nl2sql.domain.models import Failure
from nl2sql.infrastructure.inference.model import probe_model
from nl2sql.settings import Settings

from tests.contracts.test_configured_models import reply
from tests.integration.test_pipeline import plan_for


@contextmanager
def local_server(body, status=200):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            encoded = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", requests
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def local_configuration(url, api="chat_completions"):
    return Settings(
        model_mode="configured_http",
        model_api=api,
        model_endpoint=url,
        model_name="office-deployment",
        approved_model_hosts=("127.0.0.1",),
        model_auth="none",
        model_network="private",
        model_restricted_data_authorized=True,
        model_token_budget="provider",
    )


@pytest.mark.parametrize("api", ["chat_completions", "responses"])
def test_real_loopback_provider_and_cli_without_oracle(tmp_path, monkeypatch, capsys, api):
    body = reply(api)
    with local_server(body) as (url, calls):
        settings = local_configuration(
            url + ("/responses" if api == "responses" else "/chat/completions"), api
        )
        result = probe_model(settings)
        assert result.plan.reason == "metric"
        path = tmp_path / "model-settings.json"
        path.write_text(settings.model_dump_json())
        monkeypatch.setattr("sys.argv", ["nl2sql", "check-model", "--settings", str(path)])
        cli.main()
        assert len(calls) == 2
        assert json.loads(capsys.readouterr().out)["model"] == "typed_decision_received"
    assert not (tmp_path / "banking.db").exists()


def test_real_streamed_context_error_is_bounded_and_safe():
    with local_server(
        {"error": {"code": "context_length_exceeded", "message": "private prompt"}}, 400
    ) as (url, calls):
        with pytest.raises(Failure) as error:
            probe_model(local_configuration(url + "/chat/completions"))
        assert error.value.code == "MODEL_CONTEXT_BUDGET" and len(calls) == 1
        assert "private prompt" not in error.value.message


def test_cli_reports_invalid_provider_without_secrets_or_traceback(tmp_path, monkeypatch, capsys):
    path = tmp_path / "bad-model.json"
    settings = local_configuration("http://user:private-password@127.0.0.1/chat")
    path.write_text(settings.model_dump_json())
    monkeypatch.setattr("sys.argv", ["nl2sql", "check-model", "--settings", str(path)])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1
    output = capsys.readouterr().err
    assert "invalid" in output and "private-password" not in output and "Traceback" not in output


@pytest.mark.parametrize("api", ["chat_completions", "responses"])
def test_complete_api_pipeline_with_configured_http(settings, credentials, resources, api):
    body = reply(api)
    decision = {"outcome": plan_for(resources).model_dump(mode="json")}
    if api == "responses":
        body["output"][1]["content"][0]["text"] = json.dumps(decision)
    else:
        body["choices"][0]["message"]["content"] = json.dumps(decision)
    with local_server(body) as (url, calls):
        configuration = settings.model_copy(
            update={
                **local_configuration(url + "/chat/completions", api).model_dump(
                    include={
                        "model_mode",
                        "model_api",
                        "model_endpoint",
                        "model_name",
                        "approved_model_hosts",
                        "model_auth",
                        "model_network",
                        "model_restricted_data_authorized",
                        "model_token_budget",
                    }
                )
            }
        )
        with TestClient(create_app(configuration)) as client:
            response = client.post(
                "/ews-chatbot/chat",
                headers={"Authorization": "Bearer " + credentials["analyst"]},
                json={"message": "Compare regional loan exposure please"},
            )
            assert response.status_code == 200, response.text
            assert response.json()["results"] == [
                {"region": "Demo North", "loan_exposure": "175000.50"},
                {"region": "Demo South", "loan_exposure": "75000.00"},
            ]
            assert len(calls) == 1
            assert client.get(
                "/ews-chatbot/get_all_sessions",
                headers={"Authorization": "Bearer " + credentials["analyst"]},
            ).json()["sessions"]
