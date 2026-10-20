"""Actual HTTP traffic through the supported two-worker CLI and real Redis."""

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
from nl2sql.infrastructure.rate_limit import principal_key


def test_two_spawned_api_workers_share_redis_and_durable_history(
    redis_configuration, credentials, tmp_path
):
    configuration, redis_client = redis_configuration
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("NL2SQL_", "EWS_NL2SQL_"))
    }
    environment.update(
        {
            "NL2SQL_RATE_LIMIT_BACKEND": "redis",
            "NL2SQL_REDIS_URL": configuration.redis_url.get_secret_value(),
            "NL2SQL_REDIS_KEY_PREFIX": configuration.redis_key_prefix,
            "NL2SQL_REQUESTS_PER_MINUTE": "7",
        }
    )
    logs = tmp_path / "workers.log"
    with logs.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "nl2sql",
                "serve",
                "--settings",
                str(configuration.data_dir / "settings.json"),
                "--workers",
                "2",
                "--port",
                str(port),
            ],
            env=environment,
            cwd=Path(__file__).resolve().parents[2],
            stdout=output,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            start_new_session=os.name != "nt",
        )
        try:
            with httpx.Client(
                base_url=f"http://127.0.0.1:{port}",
                timeout=3,
                trust_env=False,
                headers={"Connection": "close"},
            ) as client:
                deadline = time.monotonic() + 30
                workers = set()
                while time.monotonic() < deadline:
                    assert process.poll() is None, (
                        "Worker startup exited; inspect the sanitized test log"
                    )
                    try:
                        response = client.get("/api/v1/health/ready")
                        if response.status_code == 200:
                            for line in logs.read_text(encoding="utf-8").splitlines():
                                if line.startswith('{"event": "http_request"'):
                                    workers.add(json.loads(line)["worker_pid"])
                            if len(workers) == 2:
                                break
                    except httpx.TransportError:
                        pass
                    time.sleep(0.1)
                assert len(workers) == 2, "Both spawned workers must actually serve HTTP requests"
                user = configuration.principals[0]
                headers = {"Authorization": "Bearer " + credentials[user.id]}
                assert (
                    client.post(
                        "/ews-chatbot/chat", json={"message": "Show total loan exposure by region"}
                    ).status_code
                    == 401
                )
                response = client.post(
                    "/ews-chatbot/chat",
                    headers=headers,
                    json={"message": "Show total loan exposure by region"},
                )
                assert response.status_code == 200
                assert response.json()["results"][0]["loan_exposure"] == "175000.50"
                session = response.json()["session_id"]
                history = client.get(f"/ews-chatbot/load_session/{session}", headers=headers)
                assert history.status_code == 200
                assert history.json()["messages"][-1]["results"] == response.json()["results"]
                for _ in range(5):
                    assert (
                        client.get("/ews-chatbot/get_all_sessions", headers=headers).status_code
                        == 200
                    )
                assert (
                    client.get("/ews-chatbot/get_all_sessions", headers=headers).status_code == 429
                )
                assert (
                    redis_client.zcard(
                        f"{configuration.redis_key_prefix}:rate:{principal_key(user)}"
                    )
                    == 7
                )
                assert redis_client.zcard(f"{configuration.redis_key_prefix}:chat:global") == 0
        finally:
            if os.name == "nt":
                # Kill only this test's known supervisor and its worker process tree.
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                )
            elif process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=15)
