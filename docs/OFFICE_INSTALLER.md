# Windows office installation

`install_office.py` is the single entry point for Windows x64. It installs the complete
supported Python environment from `requirements-office-windows.lock`: core services,
Oracle and Redis clients, CPU Sentence Transformers/PyTorch, and quality tools. It does
not install Oracle or Redis servers, model weights, a planning-model server or corporate
identity. Those resources must already be supplied and approved.

From the project folder, run once (use your actual approved Python and model paths):

```powershell
python install_office.py --python "C:\approved-python\python.exe" --embedding-path "C:\embedding\multi-qa-MiniLM-L6-cos-v1"
```

Omit `--python` if the existing environment or current interpreter already passes the
Python 3.13, patched SQLite, FTS5 and TLS diagnostic. Each selected runtime is checked
before environment changes. An incompatible `.venv` is renamed to a unique backup,
never deleted; stop the running app before changing its environment. Existing `.env`
and application data are preserved. An existing compatible `.venv` is reused.

When no runtime qualifies, see [the verified Windows runtime candidate](WINDOWS_RUNTIME.md).
After company approval, use `--runtime-archive "C:\approved\runtime.tar.gz"` or explicitly
select `--download-runtime`. The pinned archive's SHA256 is checked before bounded
extraction into your local application-data folder. The installer does not bypass
application control, network restrictions or approval requirements. Python package
installation uses the machine's approved pip/proxy configuration; the CPU wheel source
in the lock must be reachable or mirrored by IT.

The installer creates private files once at:

```text
%LOCALAPPDATA%\NL2SQL\office\office.json
%LOCALAPPDATA%\NL2SQL\office\office.env
```

Use `--private-root` for another protected local folder outside the repository and
synchronized storage. Windows ACLs and organizational approval must be checked locally;
creating a private-storage marker is not evidence of that approval. Reruns preserve
existing profiles. Explicitly changing `--embedding-path` backs up both profile files
before updating only the embedding configuration.

Fill the visible fields in `office.env` locally. Blank values mean unset and preserve
JSON settings; process environment variables still take precedence. No connection
secrets are supplied by this repository. The installer lists missing field names
without printing their values and exits with a blocked status until the profile is ready.
You can also enable your existing model later by filling `NL2SQL_EMBEDDING_LOCAL_PATH`
and setting `NL2SQL_EMBEDDING_MODE=local` in this private file. Leave local model ID,
version and dimension blank to infer them; generated profiles omit example encoder
placeholders so this path-only configuration works.

| Resource | Required configuration before office startup |
| --- | --- |
| Local SQLite/SurrealDB | Prepared automatically from the verified runtime and certified metadata; no server connection fields |
| Oracle query account | DSN, user, password, DBA context procedures, verified read-only grants and real approval flags |
| Oracle discovery account | Separate credentials/owners and approval flags; dictionary evidence still requires signed business/access certification |
| Authentication | Server-owned principals and token hashes or the configured JWT trust settings; user IDs do not confer grants |
| Metadata certification | Administrative trust key, reviewer configuration and valid signed approvals; setup never fabricates them |
| Planning model | Approved chat-completions endpoint, exact model/deployment ID and compatible same-origin token-count endpoint; credentials/CA where needed |
| Local embeddings | Existing saved text-model folder; the loader infers dimension, model name and a content digest |
| Redis | Approved URL/CA and `NL2SQL_RATE_LIMIT_BACKEND=redis` when using multiple API workers |

One API worker can serve multiple users. The office supervisor deliberately supports
one worker and a separate metadata monitor; its initial limits are eight overall
turns and one inference. For multiple API workers, use the VM profile/supervisor,
Redis shared admission and an approved Redis service. Installing redis-py installs
the client, not the server. Redis readiness failures block startup; no memory fallback
is substituted. These limits are configuration defaults, not measured office capacity.

After filling the private profile, rerun the same file:

```powershell
python install_office.py --check
python install_office.py --start
```

`--check` runs the full repository checker and requires the normal Git checkout and
development tools. `--start` explicitly enables provider probes with a synthetic
planning request, verifies admission, then runs the existing `office` preparation and
supervisor. Oracle preparation and valid signed metadata must pass before the API is
started. A first-time uncertified candidate remains blocked for the normal review and
publication workflow; this is not an installation failure. Nothing here enables false
approval flags or bypasses certification. Without `--start`, setup does not contact
Oracle, Redis or HTTP model services.

## Local embedding behavior

The built-in loader runs standard Sentence Transformers Transformer/Pooling/Normalize
text models on CPU, offline, with custom remote code disabled and safetensors required.
A legacy folder containing only pickle `.bin` weights must be replaced with an approved
safetensors export; it is not loaded through an unsafe fallback. No model is downloaded.
The model must remain immutable while running. Changing its files changes encoder
identity and requires compatible metadata staging/review/publication, just as changing
an HTTP encoder does. Explicit configured dimensions must match the saved model.

Embeddings retrieve semantically similar **authorized certified metadata** after exact
and FTS5/BM25 matching. They do not embed customer rows, authorize queries, certify
joins or replace the planning model. A MiniLM folder cannot act as a chat-planning SLM.
The library's local loading controls are documented in the
[Sentence Transformers API](https://www.sbert.net/docs/package_reference/sentence_transformer/model.html).

Each preparation/API/monitor process owns its loaded model. Model weights and PyTorch
memory are additional to vector-partition estimates; `retrieval_max_native_mb` is not
a hard process-memory limit. Late local results are rejected, but native inference is
not forcibly interrupted. Qualify actual model accuracy, latency, RSS and restart
behavior on the office laptop before enabling production embeddings.
