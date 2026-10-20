"""Driver contract tests use an injected pool; no Oracle service or credentials are used."""

import time
from datetime import UTC, date, datetime
from decimal import Decimal
from threading import Event, Thread

import oracledb
import pytest
from nl2sql.domain.models import Failure
from nl2sql.infrastructure.databases.oracle import OracleAdapter, OracleConfig

from tests.integration.test_pipeline import plan_for, run_plan


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.description = [(key,) for key in connection.names]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.connection.cursor_closed += 1

    def execute(self, statement, parameters=None, **options):
        self.connection.calls.append((statement, parameters, options))
        if statement != "SET TRANSACTION READ ONLY":
            if self.connection.block:
                self.connection.started.set()
                assert self.connection.cancelled.wait(2), "Cancellation watchdog failed"
                raise oracledb.DatabaseError("synthetic interrupted operation")
            if self.connection.fail:
                raise oracledb.DatabaseError("sensitive internal schema details")

    def fetchmany(self, size):
        self.connection.fetch_size = size
        return self.connection.rows[:size]


class FakeConnection:
    def __init__(self, names=("region", "loan_exposure"), rows=None):
        self.names = names
        self.rows = rows if rows is not None else [("Demo North", Decimal("17500050"))]
        self.calls = []
        self.cursor_closed = 0
        self.rollbacks = 0
        self.call_timeout = 0
        self.fetch_size = None
        self.cancelled = Event()
        self.started = Event()
        self.block = False
        self.fail = False

    def cursor(self):
        return FakeCursor(self)

    def rollback(self):
        self.rollbacks += 1

    def cancel(self):
        self.cancelled.set()


class FakePool:
    def __init__(self, connection):
        self.connection = connection
        self.acquired = 0
        self.released = 0
        self.dropped = 0
        self.closed = False

    def acquire(self):
        self.acquired += 1
        return self.connection

    def release(self, connection):
        assert connection is self.connection
        self.released += 1

    def drop(self, connection):
        assert connection is self.connection
        self.dropped += 1

    def close(self):
        self.closed = True


class FakePolicy:
    def __init__(self, reset_failure=False):
        self.applied = []
        self.resets = 0
        self.reset_failure = reset_failure

    def apply(self, connection, principal):
        self.applied.append(principal.id)

    def reset(self, connection):
        self.resets += 1
        if self.reset_failure:
            raise RuntimeError("fictional context reset failed")


def adapter_for(resources, connection, **config):
    pool = FakePool(connection)
    policy = FakePolicy()
    adapter = OracleAdapter(
        OracleConfig(
            dsn="synthetic",
            user="synthetic",
            password="synthetic",
            approved_test_environment=True,
            **config,
        ),
        resources.database.validator,
        policy,
        pool,
    )
    return adapter, pool, policy


def oracle_capability(resources, **updates):
    principal = resources.auth.principals["analyst"]
    compiled = run_plan(resources, plan_for(resources, **updates), dialect="oracle")
    return resources.database.validator.validate(compiled, principal, time.time() + 10)


def test_oracle_native_date_exact_number_read_only_and_cleanup(resources):
    connection = FakeConnection()
    adapter, pool, policy = adapter_for(resources, connection)
    cap = oracle_capability(resources)
    result = adapter.execute(cap, resources.auth.principals["analyst"])
    assert result.rows == ({"region": "Demo North", "loan_exposure": 17500050},)
    assert connection.calls[0][0] == "SET TRANSACTION READ ONLY"
    assert date(2026, 9, 30) in connection.calls[1][1].values()
    assert connection.calls[1][2] == {"fetch_decimals": True, "fetch_lobs": False}
    assert connection.fetch_size == 101
    assert 0 < connection.call_timeout <= 3000
    assert connection.cursor_closed == 1
    assert connection.rollbacks == 2
    assert policy.applied == ["analyst"] and policy.resets == 1
    assert pool.released == 1 and pool.dropped == 0
    adapter.close()
    assert pool.closed


def test_oracle_truncation_and_precision(resources):
    connection = FakeConnection(
        rows=[("Demo North", Decimal("9007199254740993")), ("Demo South", Decimal("1.01"))]
    )
    adapter, pool, _ = adapter_for(resources, connection)
    result = adapter.execute(
        oracle_capability(resources, limit=1), resources.auth.principals["analyst"]
    )
    assert result.truncated
    assert result.rows[0]["loan_exposure"] == 9007199254740993
    assert pool.released == 1
    # Driver fractional NUMBER values never pass through a float.
    assert adapter._rows(("amount",), [(Decimal("1.01"),)]) == ({"amount": "1.01"},)


def test_catalog_date_dimension_is_date_only_and_never_truncates_time(resources):
    adapter, _, _ = adapter_for(resources, FakeConnection())
    assert adapter._rows(("reporting_date",), [(datetime(2026, 9, 30),)], {"reporting_date"}) == (
        {"reporting_date": "2026-09-30"},
    )
    with pytest.raises(Failure, match="time component"):
        adapter._rows(("reporting_date",), [(datetime(2026, 9, 30, 1),)], {"reporting_date"})


@pytest.mark.parametrize("failure", ["driver", "schema", "bytes", "unsupported"])
def test_oracle_errors_are_safe_and_release_connections(resources, failure):
    connection = FakeConnection()
    kwargs = {}
    if failure == "driver":
        connection.fail = True
    elif failure == "schema":
        connection.names = ("hidden_column",)
    elif failure == "bytes":
        connection.rows = [("x" * 2000, 1)]
        kwargs["max_result_bytes"] = 1000
    else:
        connection.rows = [("Demo North", 0.1)]
    adapter, pool, policy = adapter_for(resources, connection, **kwargs)
    with pytest.raises(Failure) as error:
        adapter.execute(oracle_capability(resources), resources.auth.principals["analyst"])
    assert "sensitive" not in error.value.message and "hidden_column" not in error.value.message
    assert pool.released == 1 and policy.resets == 1


def test_failed_context_reset_discards_connection(resources):
    adapter, pool, policy = adapter_for(resources, FakeConnection())
    policy.reset_failure = True
    with pytest.raises(Failure) as error:
        adapter.execute(oracle_capability(resources), resources.auth.principals["analyst"])
    assert error.value.code == "ORACLE_CLEANUP"
    assert pool.dropped == 1 and pool.released == 0


@pytest.mark.parametrize("cancel", [False, True])
def test_oracle_deadline_and_explicit_cancellation(resources, cancel):
    connection = FakeConnection()
    connection.block = True
    adapter, pool, _ = adapter_for(resources, connection, timeout_ms=100 if not cancel else 2000)
    token = Event()
    capability = oracle_capability(resources)

    def request_cancel():
        assert connection.started.wait(2), "Driver never began execution"
        token.set()

    requester = Thread(target=request_cancel) if cancel else None
    if requester:
        requester.start()
    try:
        with pytest.raises(Failure) as error:
            adapter.execute(capability, resources.auth.principals["analyst"], token)
        assert error.value.code == ("QUERY_CANCELLED" if cancel else "QUERY_TIMEOUT")
        assert connection.cancelled.is_set()
        assert pool.released == 1
    finally:
        if requester:
            requester.join()


def test_precancelled_oracle_request_never_acquires(resources):
    adapter, pool, _ = adapter_for(resources, FakeConnection())
    token = Event()
    token.set()
    with pytest.raises(Failure) as error:
        adapter.execute(oracle_capability(resources), resources.auth.principals["analyst"], token)
    assert error.value.code == "QUERY_CANCELLED" and pool.acquired == 0


def test_expired_or_wrong_principal_capability_never_acquires_oracle(resources):
    adapter, pool, _ = adapter_for(resources, FakeConnection())
    cap = oracle_capability(resources)
    for candidate, principal in (
        (cap.model_copy(update={"expires_at": 0}), resources.auth.principals["analyst"]),
        (cap, resources.auth.principals["north_analyst"]),
    ):
        with pytest.raises(Failure):
            adapter.execute(candidate, principal)
    assert pool.acquired == 0


def test_oracle_datetime_preserves_timezone_and_null(resources):
    adapter, _, _ = adapter_for(resources, FakeConnection())
    stamp = datetime(2026, 9, 30, 12, 30, tzinfo=UTC)
    assert adapter._rows(("timestamp", "empty"), [(stamp, None)]) == (
        {"timestamp": stamp.isoformat(), "empty": None},
    )
