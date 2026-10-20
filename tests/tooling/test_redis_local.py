"""Local Redis preparation is repeatable and never overwrites existing credentials."""

import hashlib
from urllib.parse import urlparse

import pytest
from dotenv import dotenv_values

from scripts.redis_local import prepare


def test_local_setup_generates_consistent_acl_and_preserves_existing_env(tmp_path):
    existing = "NL2SQL_MODEL_MODE=disabled\n# preserved settings\n"
    (tmp_path / ".env").write_text(existing)
    path = prepare(tmp_path)
    before = {item: item.read_bytes() for item in path.parent.iterdir()}
    assert prepare(tmp_path) == path
    assert before == {item: item.read_bytes() for item in path.parent.iterdir()}
    assert (tmp_path / ".env").read_text() == existing
    acl = (path.parent / "users.acl").read_text()
    for env, key in [
        (path, "NL2SQL_REDIS_URL"),
        (path.parent / "test.env", "NL2SQL_TEST_REDIS_URL"),
    ]:
        endpoint = urlparse(dotenv_values(env)[key])
        assert endpoint.hostname == "127.0.0.1" and endpoint.port == 6380
        assert hashlib.sha256(endpoint.password.encode()).hexdigest() in acl
        assert endpoint.password not in acl
    assert "user default off" in acl
    assert "~ews:nl2sql:local:*" in acl and "~ews:test:*" in acl
    assert "+flush" not in acl and "+config" not in acl


def test_local_setup_creates_env_and_refuses_partial_state(tmp_path):
    path = prepare(tmp_path)
    assert (tmp_path / ".env").read_bytes() == path.read_bytes()
    (path.parent / "test.env").unlink()
    with pytest.raises(ValueError, match="Partial local Redis setup"):
        prepare(tmp_path)
