# Windows office installer validation — 2026-10-24

The office setup previously installed Oracle/Redis clients but did not ship the local
embedding runtime or its process-independent loader. The new `install_office.py` installs
the complete pinned Windows CPU environment, creates visible private connection fields,
preserves existing profiles/data and gates startup on configuration and resource readiness.

## Implemented scope

- Runtime diagnostic precedes environment changes; an incompatible environment is retained
  in a unique backup. The optional approved portable archive is bounded and SHA256 checked.
- Complete office lock includes core, quality tools, Oracle/Redis clients, Sentence
  Transformers 6.2.0, Transformers 5.20.2 and PyTorch 2.14.1+cpu.
- Local text models load from an existing safetensors folder on CPU with local-only loading
  and custom code disabled. Saved files determine encoder identity and inferred dimension.
- Local preparation, monitor and API use the same loader. Encoder identity remains bound
  into existing signed metadata/vector manifests and runtime compatibility checks.
- Generated private profiles accept local mode plus a folder path in the environment file;
  example encoder dimensions do not override that inference. Blank environment fields are
  unset and preserve JSON values. Actual process environment retains precedence.
- Profile/environment reruns preserve user data. Relative model paths are resolved before
  child processes change directory. Linked environments and network/private-sync storage
  are rejected; lexical Windows network paths are rejected before filesystem resolution.
- Only `--start` probes HTTP providers and Redis. Oracle preparation, current grants and
  signed certification still gate API startup. Existing active-publication restarts can
  take their principals from the publication rather than duplicate initial profile grants.

## Local evidence

Validation used a separate Windows x64 environment, preserving the existing project
environment and private data. Its linked runtime reports Python 3.13.17, SQLite 3.53.1,
FTS5 support and OpenSSL 3.5.9. This is technical qualification, not company approval.

| Check | Result |
| --- | --- |
| Complete office lock installation and `pip check` | Passed; no conflicting requirements |
| Actual native imports, SurrealDB graph lineage and vector retrieval | Passed |
| Tiny locally generated BERT text model, offline safetensors load, finite normalized vectors | Passed |
| Fresh-process model reload, identical file identity and equivalent output | Passed |
| CLI profile creation and incomplete-profile rejection before startup | Passed |
| Installer/preflight regression cases | Passed in focused runs and the full suite |
| `python scripts/check.py` in the complete office environment | Passed, exit 0 |
| Full pytest suite | 514 passed, 9 skipped; 597.38 seconds |
| Backend statement/branch coverage report | 90% total |
| Ruff, formatting, Pylint, strict Pyright, pre-commit | Passed; Pyright zero errors |
| Independent read-only review | No remaining release-blocking defect reported |

The nine local skips require the explicitly configured isolated Redis test server. The CI
workflow retains the real Redis Lua/lease/spawned-worker suite and Windows/macOS core
checks, and adds a Windows complete-package/native-embedding job. That job forces native
imports before running its optional tests so a missing runtime cannot pass as a skip.

## Qualification still required on the office machine

No office Oracle, Redis or HTTP model/embedding endpoint was contacted. No model weights
were downloaded; the native test creates tiny random synthetic weights. No actual MiniLM
accuracy, production concurrency, target-laptop memory, corporate identity or approved
storage ACLs were qualified here. The planning endpoint still needs the existing chat and
same-origin token-count contracts; a cloud endpoint URL alone does not qualify that adapter.

Install the approved Python runtime and approved external services as applicable, fill the
private profile locally and complete normal signed business/access certification. The
installer supplies clients and composition; it does not create external database servers,
planning servers or organizational approvals. See `docs/OFFICE_INSTALLER.md` for commands.
