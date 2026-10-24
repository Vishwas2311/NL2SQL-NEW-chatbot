"""Dependency-free runtime diagnostic, runnable before installing project packages."""

import json
import sqlite3
import sys
from contextlib import closing


def wal_patched(version: tuple[int, ...]) -> bool:
    """SQLite's WAL-reset fix, including its documented maintenance backports."""
    return (
        version >= (3, 51, 3)
        or version[:2] == (3, 50)
        and version >= (3, 50, 7)
        or version[:2] == (3, 44)
        and version >= (3, 44, 6)
    )


def supports_fts5() -> bool:
    """Exercise real FTS5 creation and matching using only an in-memory database."""
    try:
        with closing(sqlite3.connect(":memory:")) as connection:
            connection.execute("CREATE VIRTUAL TABLE probe USING fts5(value)")
            connection.execute("INSERT INTO probe VALUES (?)", ("runtime probe",))
            return connection.execute(
                "SELECT value FROM probe WHERE probe MATCH ?", ("runtime",)
            ).fetchall() == [("runtime probe",)]
    except sqlite3.Error:
        return False


def runtime_report() -> dict[str, object]:
    """Print intrinsic interpreter capabilities, never environment values or user data."""
    try:
        import ssl  # pylint: disable=import-outside-toplevel

        tls = ssl.OPENSSL_VERSION
    except ImportError:
        tls = None
    patched = wal_patched(sqlite3.sqlite_version_info)
    fts5 = supports_fts5()
    return {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "base_prefix": sys.base_prefix,
        "sqlite": sqlite3.sqlite_version,
        "wal_patched": patched,
        "fts5": fts5,
        "tls": tls,
        "compatible": sys.version_info[:2] == (3, 13) and patched and fts5 and tls is not None,
        "requirement": "Python 3.13, patched SQLite (3.51.3+ or approved backport), FTS5 and TLS",
    }


if __name__ == "__main__":
    report = runtime_report()
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["compatible"] else 1)
