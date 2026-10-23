"""Twenty identities exercise real HTTP admission with controlled, slow synthetic planning."""

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from threading import Barrier, Event

import pytest
from fastapi.testclient import TestClient
from nl2sql.application.ports import ModelResult
from nl2sql.bootstrap.factory import create_app
from nl2sql.domain.fingerprints import digest
from nl2sql.settings import TokenGrant

from tests.integration.test_pipeline import plan_for


@pytest.mark.parametrize("path", ["/ews-chatbot/chat", "/api/v1/chat"])
def test_twenty_distinct_users_have_bounded_admission(settings, resources, path):
    release = Event()
    active = Barrier(2)
    plan = plan_for(resources)

    class SlowModel:
        def plan(self, _question, _context, _deadline, _cancelled=None):
            active.wait(timeout=5)
            assert release.wait(timeout=10), "Synthetic workload was not released"
            return ModelResult(plan, 1, 0)

        def close(self):
            release.set()

    users = tuple(
        settings.principals[0].model_copy(update={"id": f"load-user-{i}"}) for i in range(20)
    )
    tokens = tuple(f"fictional-load-token-{i}" for i in range(20))
    configuration = settings.model_copy(
        update={
            "principals": users,
            "tokens": tuple(
                TokenGrant(sha256=digest(token), principal_id=user.id)
                for token, user in zip(tokens, users, strict=True)
            ),
            "max_concurrent_chats": 2,
            "max_concurrent_inferences": 2,
        }
    )
    with TestClient(create_app(configuration, SlowModel())) as client:
        with ThreadPoolExecutor(max_workers=20) as workers:
            futures = {
                workers.submit(
                    client.post,
                    path,
                    headers={"Authorization": "Bearer " + token},
                    json={"message": "Give me an update on total loan exposure"},
                )
                for token in tokens
            }
            rejected = []
            try:
                while len(rejected) < 18:
                    done, futures = wait(futures, timeout=5, return_when=FIRST_COMPLETED)
                    assert done, "Admission failed to reject excess work promptly"
                    for future in done:
                        response = future.result()
                        assert response.status_code == 429
                        assert response.json()["error"]["code"] == "CHAT_CAPACITY"
                        assert response.headers["Retry-After"] == "1"
                        rejected.append(response)
            finally:
                release.set()
            completed = [future.result(timeout=10) for future in futures]
        for token in tokens:
            headers = {"Authorization": "Bearer " + token}
            first = client.post(
                path, headers=headers, json={"message": "Show total loan exposure by region"}
            )
            assert first.status_code == 200
            session = first.json()["session_id"]
            followup = client.post(
                path, headers=headers, json={"message": "and 2025", "session_id": session}
            )
            assert followup.status_code == 200
            history = client.get(f"/api/v1/sessions/{session}", headers=headers)
            assert history.status_code == 200 and len(history.json()["messages"]) == 4
    assert len(completed) == 2 and all(response.status_code == 200 for response in completed)
