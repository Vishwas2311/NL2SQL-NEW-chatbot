# Office qualification update — 24 October 2026

The final six-step roadmap's local configuration, two-tier admission and schema-regression
items are implemented. Real SLM/business evaluation, upgraded-machine profiling and the
subsequent Ladybug simplification decision remain qualification gates. There was no company
connection, runtime installation, weight download, transfer, Git push or deployment.

## Roadmap status

| Step | Status | Evidence / next requirement |
|---|---|---|
| 1. Align office configuration | Implemented locally | Both `config/office.example.json` and `config/office.env.example` target 100000 input-plus-output context tokens. This must match the selected runtime's actual per-request allocation. Generic application/development defaults stay 8192. |
| 2. Two-tier admission | Implemented locally | Overall turn admission remains in HTTP transport. `application/inference.py` takes a separate model lease only around the provider call. Bootstrap shares that planner/admission across catalog versions and owns cleanup. Memory/Redis adapter logic is reused. |
| 3. Schema regression | Implemented locally | End-to-end chat-to-HTTP-payload tests assert schema absent from metadata in json_schema mode and present for json_object/text_json. The existing schema-selection implementation was retained. |
| 4. Real SLM evaluation | Pending actual approved runtime/corpus | Existing provider and model-comparison seams remain available. Synthetic fixtures do not replace 50+ independently reviewed, held-out business questions on the selected SLM. |
| 5. Hardware profiling | Pending upgraded machine | Measure native/unified memory, KV cache and prefill/total latency at 1, 2 and 4 model slots; do not substitute Python heap tracing for runtime memory measurements. |
| 6. Ladybug evaluation | Deferred until model/catalog qualification | No replacement was made. Any approved migration must preserve certified path filtering, alternative-path checks, lineage, snapshot compatibility and lease/retirement behavior. |

## Behavior and limits

The office examples select **one API worker, eight overall chat slots and one inference slot**.
Twenty users can share those bounded resources; these settings are provisional rather than
measured office throughput. There is no unbounded inference queue.

- Exact catalog templates and recognized deterministic follow-ups bypass model admission.
  Flexible model-based follow-ups take an inference slot.
- Overall request, per-principal, session and database limits still apply. An outer-full
  system can reject a template; there is no unconditional priority or sub-15ms guarantee.
- Inference saturation returns `INFERENCE_CAPACITY`/429 with `Retry-After`; outer saturation
  remains `CHAT_CAPACITY`/429. Current per-user turn admission remains unchanged. Inner
  admission allows one active inference per tenant/subject.
- Provider success, typed clarification and failure release inner capacity before later
  SQL execution/history work. Expired requests cannot enter the model. Redis lease release
  uncertainty does not authorize SQL execution.
- All active/retired catalog bundles in one API process share the same inference planner.
  Multiworker Redis uses `<deployment-prefix>:inference:chat:*` keys, independent of outer
  chat keys. It does not share limits with the outer chat counter or replace current grants.
- Two Redis clients/pools per worker are now owned by the outer and inner admission
  lifecycles. Allow up to twice the configured per-client connection ceiling. The existing
  ACL commands must cover the inference namespace. One worker can use memory admission.

The inner lease includes token counting and any provider retries. Context construction and
retrieval are still bounded by their existing controls and the inherited request deadline.
The application does not allocate runtime context/KV memory; the actual model server does.
The default metadata byte ceiling remains 64000 and output reserve 1200 tokens plus safety
margin. Supporting a 100000-token request ceiling does not require filling it.

The office model and turn timeouts remain 60 and 120 seconds. Long-input runtime profiling
must verify that the chosen operating workload fits those bounds. More context/RAM does
not extend the compiler's supported operations, certified joins, row limits or SQL safety policy.

## Verification

Focused HTTP/provider tests passed for both EWS and typed chat contracts, including a slow
model alongside another user's template/follow-up, prompt inference overload, same-user
denial, retry recovery and provider timeout/invalid-output cleanup. Unit checks cover expired
requests, shared admission across catalog planners and failed-startup resource cleanup.

The mandatory `python scripts/check.py` run completed successfully:

| Check | Result |
|---|---|
| Ruff correctness / imports | Passed |
| Ruff formatting | Passed; 180 Python files |
| Pylint | 10.00 / 10 |
| Strict Pyright | Zero errors, warnings or information diagnostics |
| Pytest, including security, compiler and API contracts | **466 passed, 9 skipped, 1 warning** in 195.63 seconds |
| Pre-commit correctness / formatting / strict typing | All three passed |
| Original UI asset hashes | Unchanged |

The warning is the existing Starlette test-client dependency deprecation. The raw local log
is `.local/two-tier-full-check-20261024.txt`. No quality thresholds or existing safety
assertions were removed. A real Redis independent-client test was added for shared inner
leases and separate outer keys. The
explicit isolated loopback test service did not respond to the local probe; mocks do not
qualify live Lua behavior or multiworker Redis operation.

## Qualification and source handover

Use the updated OPERATIONS.md procedure for the actual approved model/token counter,
50+ held-out business questions, 1/2/4-slot hardware profiling and the 20-identity HTTP workload.
No working selected endpoint or approved business evaluation corpus was supplied in this task.
Do not use the example endpoint as evidence that a real runtime is connected.

The reviewed local interpreter still links SQLite 3.50.4. Restricted office preflight requires
an approved patched native SQLite build (3.51.3+ or documented fixed maintenance branches).
Recreate the virtual environment on the target; pip upgrades do not patch stdlib SQLite.
Keep real profiles, credentials, inventories, reviews and backups outside source/sync folders.

Previous source ZIPs predate this update. The new
`dist/nl2sql-office-source-2026-10-24-100k.zip` includes a verified manifest and the latest
public source, examples, tests and documentation. Packaging checks CRC, every manifest hash
and equality with the current included source files. It contains no
populated secrets, runtime databases, model weights or Windows virtual environment.

The architecture is prepared for controlled office qualification. This report is not production
approval, a capacity promise, a full penetration test or evidence of live Oracle/SLM integration.
