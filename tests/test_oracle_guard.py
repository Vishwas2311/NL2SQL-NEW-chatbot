"""Oracle remains closed without explicit environment authorization."""

import pytest
from nl2sql.domain import Failure
from nl2sql.oracle import OracleAdapter, OracleConfig


def test_oracle_approval_gate_precedes_any_driver_connection(resources, monkeypatch):
    def forbidden_connection(**_kwargs):
        pytest.fail("An unapproved Oracle connection was attempted")

    monkeypatch.setattr("nl2sql.oracle.oracledb.create_pool", forbidden_connection)
    config = OracleConfig(dsn="fictional-only", user="fictional-only", password="fictional-only")
    with pytest.raises(Failure) as error:
        OracleAdapter(config, resources.database.validator, object())
    assert error.value.code == "ORACLE_NOT_APPROVED"
