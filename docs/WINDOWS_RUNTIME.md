# Windows runtime candidate — 24 October 2026

The earlier stock CPython recommendation did not solve the SQLite requirement. Installing
a Python version number alone does not establish which SQLite library it loads.

We found and exercised this **different distribution**, independently of the existing
development `.venv`, installed Python programs, application settings and runtime data:

| Item | Verified candidate |
|---|---|
| Provider | Astral python-build-standalone |
| Release | `20261021` |
| Architecture | Windows x64, ordinary GIL-enabled CPython |
| Python | `3.13.17` |
| Linked SQLite | `3.53.1` |
| FTS5 | Actual create/insert/MATCH test passed |
| Python TLS | `OpenSSL 3.5.9 29 Sep 2026` |
| Installer | None; portable runtime archive |

[Pinned upstream release](https://github.com/astral-sh/python-build-standalone/releases/tag/20261021) ·
[Exact upstream archive](https://github.com/astral-sh/python-build-standalone/releases/download/20261021/cpython-3.13.17%2B20261021-x86_64-pc-windows-msvc-install_only_stripped.tar.gz) ·
[Provider documentation](https://docs.astral.sh/python-build-standalone/)

Archive: `cpython-3.13.17+20261021-x86_64-pc-windows-msvc-install_only_stripped.tar.gz`

SHA-256, checked against the downloaded bytes and upstream GitHub asset digest:

```text
56cde3b1a1dcc36576753cb408ee0c3568d211baafa0eee40423adc147c480f2
```

This is a technically verified candidate, **not a claim of company approval**. Company IT
must approve this distribution/hash or supply an equivalent approved Python 3.13 build.
Do not evade installer, application-control or antivirus policy. Local checks do not prove
the archive will be allowed on the office laptop.

Local validation: 488 full-suite tests passed, 9 real Redis tests were unavailable, and
coverage remained 90%. The additional missing-TLS diagnostic test passed separately.
Ruff, Pylint, strict Pyright and the final pre-commit rerun passed. The actual office
SQLite/FTS5 preflight passed without an override. See the
[qualification record](../reports/windows-runtime-qualification-2026-10-24.json) for scope,
the resolved hook-staging interruption and synthetic load results.

## Inspect before changing an environment

The new diagnostic uses only Python's standard library and a disposable in-memory
SQLite database. It does not load `.env`, open application databases, contact Oracle/model
services, install packages or create a virtual environment. After IT approval, extract the
complete archive into `%LOCALAPPDATA%\NL2SQL-Runtimes\20261021` (or the location IT selects).
It contains a `python` directory. From the project root in PowerShell:

```powershell
$officePython = Join-Path $env:LOCALAPPDATA 'NL2SQL-Runtimes\20261021\python\python.exe'
if (-not (Test-Path -LiteralPath $officePython)) { throw 'Extract the approved runtime first.' }
& $officePython -I backend/nl2sql/bootstrap/sqlite_runtime.py
```

If IT selects a different location, set `$officePython` to that actual executable path.
This uses a user-writable location and does not require creating folders in Program Files.
The output records the executable, base interpreter, Python/SQLite/TLS versions, FTS5,
WAL patch status and `compatible`. Exit 0 means those intrinsic checks pass; exit 1 means
they fail. It does not certify company approval, storage ACLs or external integrations.

SQLite's [official WAL advisory](https://sqlite.org/wal.html#walresetbug) identifies the fix
in 3.51.3 and the 3.50.7/3.44.6 maintenance backports. The existing accepted version policy
is retained. FTS5 is now also checked by the office preflight using an actual query.
The candidate's 3.53.1 satisfies the mainline requirement directly.

## Rebuild only after verification

1. Obtain company approval, verify the archive hash and extract the complete runtime into
   approved local storage. Do not copy individual DLLs into system Python or Program Files.
2. Run the diagnostic above and require `compatible: true`. This can be done before pip
   or any project dependency is installed. Keep its output for IT.
3. Stop the office supervisor, API and monitor. Back up the existing environment and
   protected data. Preserve `.env`, source profiles, grants, approvals, catalogs and data.
   Keep the old `.venv` in an approved backup location; do not delete it as a setup shortcut.
4. From the project root, invoke setup with the verified interpreter after the previous
   `.venv` has been safely set aside:

   ```powershell
   & $officePython setup_env.py --office
   ```

   Setup now checks the selected interpreter **before creating `.venv` or installing
   packages**, checks a newly created environment again, and never overwrites `.env`.
   If `.venv` already exists, it checks that environment's actual interpreter first. A
   patched launcher cannot silently repair an existing `.venv` linked to old Python.
5. Install the pinned development tools when running the full checker:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe -m pip check
   .\.venv\Scripts\python.exe scripts/check.py
   ```

   Enter one command at a time. Activation and changing PowerShell execution policy are
   unnecessary when using the executable directly. The tracked root file
   `export_project_to_txt.py` must be retained: `scripts/strix_scan.py` imports it.
   Restore an accidentally deleted tracked file only after checking local changes.
6. Apply the [SurrealDB migration](SURREALDB_MIGRATION.md), including fresh signed managed
   metadata publication. Passing native SQLite checks alone does not qualify Oracle,
   corporate identity, model capacity or the office storage configuration.

For portable transfer, transfer the upstream runtime archive and source separately; create
the virtual environment on the destination. Do not copy our development `.venv` or private
runtime data to the office laptop. The tested archive is retained under the ignored local
runtime-qualification directory; binaries and virtual environments are not committed to Git.
