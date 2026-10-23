# Application architecture review — 24 October 2026

Historical review: the subsequent fixes and verification are recorded in
[the architecture remediation report](architecture-remediation-2026-10-24.md).

What this repo does: A governed NL-to-SQL backend retrieves certified metadata, asks a configured model for a typed plan, validates that plan, compiles SQL deterministically and independently authorizes read-only execution. It persists owned conversations and maintains approved metadata publications separately from the query path.

The target assessed here is **20 users on one company-managed machine, primarily using an SLM**. Twenty users does not imply 20 simultaneous inference requests. Hardware, the exact model/runtime and peak request rate remain undecided. This is an architecture review of the current working tree, including untracked implementation files, not an approval of a running office deployment.

## Decision and scores

**Retain the modular monolith and existing storage responsibilities. Do not approve the current design for unrestricted production and long-term maintenance yet.** Approve the architectural direction, address the identified gaps incrementally, then qualify the real workload. A rewrite, microservices, another database, an agent framework and a distributed job platform are not justified by 20 users.

| Score | Assessment | Reason |
|---|---:|---|
| Application architecture | 7.5/10 | Strong trust boundaries and coherent control/data separation; incomplete conversational and upgrade contracts |
| Maintainability | 6.5/10 | Good ownership and tests, weakened by configuration coupling, mixed chat responsibilities and missing persistent-format evolution |
| Extensibility | 7.0/10 | Useful provider ports and declarative metrics; new query operators and local runtime registration need coordinated work |
| Scalability of design | 6.0/10 | Sensible single-VM boundaries and admission controls; partition duplication and request-time resource adoption need explicit budgets |
| Code organization | 8.0/10 | Clear packages and tested import direction; several central files are becoming coordination hotspots |

Scores are engineering judgments against this application and its 20-user target. They are not benchmark results, probabilities of correctness or ratings for million-user deployment.

## Review scope and evidence

- Mapped all **81 Python modules / 12,739 lines** under `backend/nl2sql`, including the synthetic evaluation package. Parsed imports and function bodies across this package.
- Read the README, ownership map, architecture/walkthrough, relevant numbered design sections, dependency/build configuration and important test groups. Traced HTTP/authentication, admission, sessions, retrieval/context, model inference, compilation, execution, metadata publication and resource retirement.
- No internal import cycle was found in the static module graph. No relative imports are currently present. Existing layer-boundary tests passed.
- No identical nontrivial function body was found by the AST comparison used here. This does not prove absence of conceptual duplication.
- Fresh verification: **70 passed** for architecture boundaries, API/error contracts, tokenizer contracts, rate admission and session access; **126 passed** for compiler security, advanced SQL, metadata lifecycle, native graph, retrieval and office launcher. Total **196 passing selected tests**, with one existing Starlette test-client deprecation warning.
- Two synthetic probes confirmed the keyword rejection described in finding 8 and the future schema-evolution hazard described in finding 1. Neither contacted a provider or business database.
- Reused the earlier same-day synthetic context/cache/retrieval measurements where explicitly identified. They are not fresh production benchmarks.
- Application source and UI assets were not changed. The full `scripts/check.py` suite was not rerun for this report-only review. Earlier full-suite results are historical evidence, not this review's test count.

Local evidence: `.local/final-architecture-static-20261024.json`, `.local/final-architecture-probes-20261024.json`, `.local/final-architecture-review-20261024-tests.txt`, `.local/final-architecture-lifecycle-20261024-tests.txt`.

## Existing architecture and responsibilities

```text
HTTP/EWS adapter
  -> authenticated current principal + request admission
  -> pinned approved runtime bundle
  -> owned session + route selection
  -> exact/BM25 retrieval [+ configured embeddings/vector fusion]
  -> authorized bounded context -> SLM typed QueryPlan
  -> plan/grain/time/access validation + certified graph traversal
  -> authorized entity lookup -> validation
  -> deterministic SQLGlot compilation
  -> independent SQL inspection + signed execution capability
  -> bounded read-only executor -> exact Decimal formatting
  -> owned history -> current authorization -> response

Separate metadata control path:
discovery -> reconciliation/impact -> candidate -> signed review
  -> compatible resource checks -> atomic publication -> worker adoption/drain
```

| Component | Actual responsibility | Architectural decision |
|---|---|---|
| Oracle query adapter | Office business rows; typed binds, read-only transactions, bounded results, context reset | Keep; live office behavior unqualified |
| Oracle discovery adapter | Physical dictionary evidence and drift observations | Keep; discovery cannot invent business/access certification |
| SQLite metadata repository | Catalog/grant snapshots, review evidence, publication pointer, quarantine and scheduling state | Keep as local authority |
| SQLite sessions | Owned messages/results and last typed plan, optimistic updates | Keep; stored results are history, not a fresh answer cache |
| Synthetic SQLite business DB | Fictional known-answer execution | Testing/demo only |
| In-memory SQLite FTS5/BM25 | Authorized metric/schema keyword retrieval per distinct metric-grant set | Keep; fix full-text budget accounting |
| Ladybug graph files | Rebuildable certified joins and lineage, opened read-only by workers | Keep; do not promote the projection to policy authority |
| Ladybug vector projections | Exact cosine search over metric vectors, per nonempty grant partition | Optional with a qualified encoder; no ANN extension is in use |
| Managed embedding cache | Bounded vector reuse; optional JSON restart snapshots | Keep RAM reuse when enabled; simplify disk persistence |
| Redis | Shared request quotas and active-chat leases | Required by the current multiworker design; not a metadata/session/result store |
| SLM endpoint | Proposes a typed plan from supplied evidence | Keep separate from execution authority; qualify its actual context/output behavior |

FAISS and NetworkX are not current runtime dependencies. Pure Python structural adjacency remains legitimate certification/drift evidence; it is not a second persistent graph database. Graphify output is developer navigation, not runtime RAG data.

## Must fix before the requested production approval

These are approval blockers or conditional workload blockers. This review did not establish a current catastrophic data-loss exploit, and does not label every refactoring opportunity critical.

### 1. Persistent records have no explicit upgrade architecture

- **What this is:** Session and metadata stores create tables with `CREATE TABLE IF NOT EXISTS`, then parse stored JSON directly into the current Pydantic contracts. `BundleSpec.id` hashes its current serialized model.
- **Problem:** There is no repository schema-version/migration runner or versioned bundle/message reader. A synthetic probe adding a defaulted field to `BundleSpec` changed the reconstructed identity of otherwise unchanged stored content. This is a demonstrated future-upgrade hazard, not observed corruption of today's records.
- **Fix:** Add small ordered SQLite migrations and explicit serialized-format versions/readers. Verify existing signed payloads using their original format and preserve their original identity; semantic changes need a newly reviewed publication. Test an old-release database upgraded to the new release and safe rejection of unsupported future formats.
- **If skipped:** An ordinary feature release can turn valid history or publications into unreadable/integrity-failing records. Operators may be tempted to reset data or bypass signatures.

Sources: `infrastructure/sessions.py:29,92,129`; `infrastructure/metadata/store.py:43,76`; `domain/metadata.py:77,90`; `domain/models.py:284`.

Do not silently rewrite signed snapshots, synthesize approvals or use `model_copy` as a migration mechanism. Derived graph files also need an explicit rebuild/engine-format upgrade procedure. Keep authority records separate from disposable projections.

### 2. Retrieval's advertised resource boundary is incomplete

- **What this is:** Retrieval allocates FTS and native vector resources per distinct metric-grant tuple, then each API worker owns its copies.
- **Problem:** The FTS byte check counts metric documents but omits the separately inserted `schema_docs`. Prior synthetic evidence showed an accepted catalog with about 12.17 MB of schema text while the counted metric text was only 1,592 bytes. The vector component cap also applies across duplicated partitions, not just unique metrics.
- **Fix:** Preflight all authorized metric and schema text, vector dimensions/components and partition counts before expensive allocation. Report aggregate projected budgets per worker and overlapping bundle. Keep authorization partitions; do not weaken filtering to save memory.
- **If skipped:** A seemingly small catalog or a change in grants can fail activation or consume much more memory than its configured text bound suggests.

Sources: `infrastructure/retrieval/lexical.py:81-135`; `infrastructure/retrieval/vector_index.py:31`; `infrastructure/metadata/builder.py:48`.

Concrete sizing example: 20 distinct grant sets, each containing 100 vectorized metrics at 768 dimensions, require 1,536,000 vector components, exceeding the current 1,000,000-component cap. If users share a grant set, they share that partition. Twenty configured 32 MiB native partition buffers represent 640 MiB of nominal buffer budgets per worker, **not measured committed RSS**. Exact cosine is reasonable at this metadata scale; an ANN system is not automatically needed.

### 3. Authentication can trigger expensive adoption outside the chat deadline

- **What this is:** `Authenticator.refresh_hook` invokes `RuntimeManager.reload`; after a publication, reload verifies the record and constructs graph/search/executor resources under a reload lock.
- **Problem:** This may happen during authentication before chat-slot admission and before `ChatService` starts its request deadline. Concurrent requests, including session reads, can wait behind adoption. The ordinary unchanged-pointer path is cheap; this is specifically the publication transition.
- **Fix:** Define a bounded request lifecycle covering adoption waits and use-case work. For the first small deployment, an explicit drain/reload window after publication is simpler than sophisticated asynchronous hot adoption. If hot adoption is required, prewarm with bounded waiting and return a safe retry status when current resources are unavailable. Preserve current-grant checks throughout.
- **If skipped:** A configured 120-second chat budget does not describe the entire request, and metadata publication can produce a confusing latency spike for all 20 users.

Sources: `infrastructure/auth.py:30,39`; `bootstrap/managed.py:133`; `bootstrap/runtime.py:234-290`; `application/chat.py:314,331`.

The providers and Oracle adapter have useful local timeout/cancellation checks. However, browser disconnect cancellation is not propagated through the whole application, and the core execution port does not expose the Oracle adapter's optional cancellation argument. Do not advertise end-to-end cancellation. Passing one deadline explicitly at orchestration boundaries is useful; threading request IDs through every pure helper is unnecessary.

### 4. The SLM cannot explicitly request clarification through its contract

- **What this is:** `ModelResult` contains a mandatory `QueryPlan`; structured HTTP inference asks only for that schema.
- **Problem:** The application can clarify particular aliases, dates, entities and hard-coded questions, but the model cannot return a valid typed “I need this business distinction first” outcome. For an ambiguity not recognized by deterministic rules, it must choose a plan or produce an invalid response. A structurally valid authorized plan still may misunderstand intent.
- **Fix:** Use a small discriminated planning result: a plan proposal or a bounded clarification request. Validate any offered choices against the authorized catalog. The clarification branch must perform no SQL execution and must reauthorize the next turn.
- **If skipped:** Some uncertain SLM outputs become provider errors or valid-looking answers to the wrong interpretation.

Sources: `application/ports.py:118,128`; `infrastructure/inference/model.py:130-247`; `application/chat.py:169-223`.

This is especially important for an SLM. Embeddings and a strict output schema do not themselves prove understanding.

### 5. Conversational context exists in storage but is missing from general model planning

- **What this is:** The session stores the last plan, and `_followup` recognizes a fixed command list plus a date pattern.
- **Problem:** Flexible planning receives the new question and retrieved metadata, without the previous authorized plan/slots. “Break that down by branch” therefore has no general way to preserve the prior metric and filters unless it happens to match a supported command.
- **Fix:** Supply a compact typed previous-plan context, only after current authorization and catalog compatibility checks. Merge only explicit changes, validate the complete new plan and clarify missing references. Retain the existing cheap deterministic follow-ups.
- **If skipped:** The product remains a bounded report chatbot with a few follow-ups; it does not fulfill broad conversational continuity.

Sources: `application/chat.py:110-167,204-216`; `application/context.py:10`; `domain/sessions.py:30`.

Do not inject unrestricted transcript text or prior result rows. If broad follow-ups are explicitly excluded from the product, document that narrower scope instead of implementing an unnecessary conversational engine.

### 6. Production workload evidence does not exercise the SLM request design

- **What this is:** Existing synthetic load tests call `resources.service.chat` using the same principal, a certified template and no real inference.
- **Problem:** That benchmark deliberately bypasses HTTP admission and model calls. It cannot establish capacity for 20 distinct users asking flexible questions, even if a 50-caller synthetic result looks good. Redis tests exercise real-server behavior only in their explicitly configured environment; they were not run in this review.
- **Fix:** Add a workload acceptance fixture for 20 distinct identities, mixed routes, fresh sessions, repeated turns and a 20-request burst. Exercise HTTP admission using controlled slow/failing providers first, then qualify the selected approved SLM and Oracle. Measure accepted versus rejected requests, latency, model validity, results, memory and adoption behavior.
- **If skipped:** The application can pass all current synthetic checks while delivering unacceptable busy responses or model timeouts for the intended users.

Sources: `evaluation/load.py:29-136`; `scripts/concurrency_benchmark.py`; `tests/integration/test_redis_workers.py`; `config/office.example.json:33`.

No unbounded queue is recommended. Decide whether a finite wait or a clear busy response is the product contract. A queue becomes necessary only if automatic waiting is required; it is currently absent.

## Should fix

### 7. Persistent embedding snapshots run inside the encoder's shared critical section

- **What this is:** One lock serializes encoding and cache updates. Each miss, including a new question, can checksum and serialize the entire optional disk cache while holding that lock.
- **Problem:** An optimization for restart reuse becomes request-path work for every unique question. Earlier synthetic evidence produced 33,171,457 bytes of vector-entry JSON for 2,048 entries at 768 dimensions, exceeding the 20 MB snapshot limit; one save attempt took 1.403 seconds and wrote no snapshot. This single timing is not a latency benchmark.
- **Fix:** For initial qualification, leave disk persistence disabled while retaining bounded RAM reuse. If restart persistence is required, persist metadata vectors during preparation or at a controlled checkpoint, with dimension-aware byte limits and writes outside the encoding critical section. Keep atomic replacement and invalid-cache rebuilding.
- **If skipped:** Concurrent hybrid questions can wait behind serialization that provides no useful restart cache.

Sources: `infrastructure/retrieval/embeddings.py:147-211`; `infrastructure/retrieval/embedding_cache.py:82`.

### 8. Core routing still contains demo-specific semantics and an overbroad keyword gate

- **What this is:** The generic chat service contains synthetic template mappings, hard-coded region/account follow-ups and fixed loan clarification phrases.
- **Problem:** Domain vocabulary is coupled to orchestration. The probe “Give me an update on total loan exposure” returns `UNSUPPORTED` because of the word `update`, before the model is called. This is a confirmed false rejection, not an SQL security bypass.
- **Fix:** Move synthetic report definitions into the already-supported catalog templates. Isolate the small supported follow-up policy. Replace broad word blacklisting with an explicit intent policy while retaining typed plans, independent SQL checks and read-only execution.
- **If skipped:** New business domains require editing central chat code, and normal read-only questions can fail for unrelated wording.

Sources: `application/chat.py:43-67,110-167,184-195`; `domain/models.py:308`.

### 9. Optional retrieval is made mandatory by the office launcher

- **What this is:** Core retrieval supports `encoder=None`, but `run_office` accepts only `private_http` or `local` embeddings.
- **Problem:** A valid lexical-only operating mode cannot use the standard automatic office preparation/monitor launcher. An encoder dependency becomes a deployment requirement without real quality evidence.
- **Fix:** Permit the approved lexical-only profile and build vectors automatically whenever a real encoder is enabled. Keep the disabled/fake/restricted boundaries distinct. Changing retrieval identity still requires a compatible reviewed publication, not modification of an existing approval.
- **If skipped:** An unavailable or unqualified embedding runtime blocks otherwise usable lexical reporting.

Sources: `cli/office.py:40`; `infrastructure/retrieval/embeddings.py:233`; `infrastructure/retrieval/lexical.py:210`.

The earlier requirement for automatic vector construction explains how this restriction arose. It is an unnecessary launcher coupling, not evidence that the vector implementation was pointless.

### 10. Runtime configuration is validated in pieces and implicitly reread

- **What this is:** A broad mutable `Settings` object, Oracle execution/discovery settings, source profiles, trust-anchor environment reads and process-scoped dotenv injection all participate in construction.
- **Problem:** Passing a validated application settings object does not describe every dependency. For example, `RuntimeFactory` calls `oracle_executor` without explicit Oracle settings, so another environment-derived object is constructed during runtime adoption. General `pool_size`, timeout and result settings are distinct from Oracle's similarly named settings.
- **Fix:** Resolve configuration once at each process composition root, retaining separate discovery/query credentials and trust authority. Pass the typed adapter configuration/factories explicitly. Preserve current public env keys; do not force a giant configuration migration merely to nest fields.
- **If skipped:** Tests and startup commands can agree on application settings while later adapter construction uses surprising defaults or process state.

Sources: `settings.py:36,184-220`; `bootstrap/runtime.py:95-100`; `infrastructure/databases/oracle_factory.py:18,76`; `infrastructure/metadata/config.py:67`; `cli/metadata.py:221`.

Separation of discovery and query credentials is correct and must remain. Environment loading at process startup is normal; hidden reads from deeper factories are the issue.

### 11. The chat service and execution port expose too many connected responsibilities

- **What this is:** The 342-line `ChatService` class handles routing, follow-up mutation, entity resolution, compilation sequencing, result formatting, response text and persistence. `QueryExecutor` also exposes the concrete SQL validator, which chat reaches through the executor.
- **Problem:** A display-format or conversational change shares a file with the execution pipeline. Alternate executors must expose validation machinery as part of the persistence interface. The catalog provider additionally relies on Python object identity to detect changes.
- **Fix:** Extract only the existing routing/follow-up and Decimal result-formatting jobs into application-owned functions/modules. Keep orchestration in `ChatService`; inject the SQL validator explicitly alongside execution. For bundle-bound services, a pinned `Catalog` is simpler than a provider plus `is` identity assertion, provided the standalone reload guard remains equivalent.
- **If skipped:** Developers changing different features contend on the same class and can disturb unrelated stages.

Sources: `application/chat.py:70-411,338,352`; `application/ports.py:24,171`; `bootstrap/runtime.py:124`; `bootstrap/resources.py:122`.

This is a growing orchestration hotspot, not a reason to create a service class for each line of the pipeline. The 565-line `SQLValidator` is also a hotspot, but its independent enforcement is cohesive and required. Split operation-specific checks only when extending those operations; never replace it with a call back to the compiler.

### 12. Embedding transport reuses the complete planning adapter at the wrong level

- **What this is:** `PrivateEmbedding` constructs a `PrivateHTTPModel` with copied/replaced model endpoint settings just to reuse its client and endpoint policy.
- **Problem:** Embedding construction is coupled to the planning provider's settings and lifecycle even though it never performs planning. Changes to the planning adapter can unintentionally affect embeddings.
- **Fix:** Reuse small endpoint-validation/client-construction functions between the two adapters. Keep their payloads, timeouts and response validation separate. No general transport framework is needed.
- **If skipped:** Apparently isolated planning changes require embedding regression work and can break an unrelated integration.

Source: `infrastructure/retrieval/embeddings.py:58-69`; `infrastructure/inference/model.py:95-128`.

### 13. Transport behavior and storage error ownership are inconsistent

- **What this is:** EWS and typed chat routes share the use case, but EWS alone emits the `pipeline` stage event after successful completion. The HTTP layer imports `sqlite3` and translates its errors directly; the shared domain `Failure` carries an HTTP status.
- **Problem:** Identical work has different diagnostic visibility depending on endpoint, and failures bypass the success-only pipeline event. Storage implementation knowledge leaks into transport, while HTTP knowledge lives in a domain exception.
- **Fix:** Reuse one small route invocation boundary for admission and completion/failure metrics, then map responses separately. Translate adapter storage failures into application failures at the adapter boundary. Centralize HTTP mapping while preserving stable public error codes and response shapes; do not convert all existing errors in one risky rewrite.
- **If skipped:** A client migration to `/api/v1/chat` changes observability, and replacing session storage also requires transport changes.

Sources: `api/app.py:60,147-170,195-217`; `domain/models.py:22`; `infrastructure/sessions.py`; `infrastructure/metadata/store.py`.

Correlation, sanitized responses and stage timings already exist. This finding is about consistency and ownership, not a request for a new monitoring service.

### 14. Registered local extensions lack an explicit stock-process bootstrap path

- **What this is:** Model and local-embedding factories can be registered into module globals. Tests register them; the stock CLI/worker composition does not register a concrete installed local embedding runtime.
- **Problem:** A configured existing weights path alone cannot make `embedding_mode=local` work. A registration performed in another process is not inherited by a freshly spawned CLI/worker process.
- **Fix:** For a selected installed runtime, wire its approved registration explicitly in each process composition root, or use the existing private HTTP adapter and document that local mode remains an integration seam. Do not add plugin discovery, arbitrary import strings or automatic weight downloads.
- **If skipped:** “Swappable model” is mistaken for “every installed runtime works by configuration alone.”

Sources: `infrastructure/retrieval/embeddings.py:223-251`; `infrastructure/inference/model.py:304-329`; `bootstrap/factory.py:35`; registration references in `tests/contracts/test_hardening_provider_contracts.py`.

## Nice to have / improve as the application grows

### 15. Reduce redundant SLM context after measuring the real tokenizer

- **What this is:** `build_context` includes the QueryPlan JSON schema, and default `json_schema` inference includes it again in `response_format`.
- **Problem:** Earlier one-metric synthetic context was 15,225 JSON bytes, including a 5,116-byte schema. This is avoidable duplication in the default mode; `json_object` and `text_json` need different treatment. Exact token/latency savings are unmeasured.
- **Fix:** Qualify a concise allowed-ID context and one authoritative output-schema location per provider mode. Retain the full runtime-token counting and output reserve. Do not remove required definitions or weaken plan validation to fit a prompt.
- **If skipped:** Some of an SLM's limited input budget is spent on repeated contract text rather than useful business evidence.

Sources: `application/context.py:71`; `infrastructure/inference/model.py:141-147`; `infrastructure/inference/token_budget.py:22`.

### 16. Enforce future boundaries and retention rather than adding more layers

- **What this is:** `domain/models.py` is imported by 56 backend modules; `Settings` by 20. Layer tests check absolute package imports and a small list of forbidden domain I/O modules. Metadata history and graph versions are retained; safe automatic pruning is not implemented.
- **Problem:** Central contracts are legitimate shared dependencies, but unrelated changes increasingly meet in the same file. The boundary test would not catch a future relative import. Indefinite derived-file growth and unknown older-version reader support make long-term operation harder.
- **Fix:** Split contracts by semantic catalog, plans and results when those sections change, with direct owning imports. Resolve relative imports in the architecture test and test its detection with a synthetic violating file. Define approved retention and a dry-run maintenance path for unreferenced projections; never delete active or leased files. Add previous-version and target-platform test fixtures.
- **If skipped:** Navigation, merge coordination and historical-state maintenance become steadily more expensive.

Sources: `domain/models.py`; `tests/tooling/test_architecture.py:27`; `infrastructure/metadata/store.py:114,204`; `infrastructure/graph.py:17`; `.github/workflows/backend.yml`.

There is no current relative-import violation, and file length alone is not a defect. The main CI quality job is Windows; the Redis job is Linux. A real target-platform run remains important if the office target is macOS.

## All 20 requested design areas

For each area, all nine requested questions are answered below. “None identified” means no evidence justified that specific criticism or addition; it does not mean perfection.

### 1. Overall application architecture

- **Well designed:** Modular monolith; separate query and metadata control paths; clear authority versus projection.
- **Poorly designed:** Request handling can become the resource-adoption coordinator.
- **Over-engineered:** Multiple operating modes expose complexity before qualification; the monolith itself is appropriate.
- **Under-engineered:** Persistent upgrades and workload acceptance contracts.
- **Simplify:** One documented production composition; explicit publication/reload procedure.
- **Modularize:** Existing query orchestration versus preparation ownership; no new services.
- **Refactor:** Findings 1, 3 and 10.
- **Remove:** No major architecture component; no justified wholesale rewrite.
- **Add:** Versioned upgrades and measured 20-user acceptance evidence.

### 2. Module organization

- **Well designed:** Domain/application/infrastructure/API/bootstrap/CLI ownership is clear and tested.
- **Poorly designed:** Central model and port files mix several change domains.
- **Over-engineered:** No evidence of a needless package explosion; small package markers are harmless.
- **Under-engineered:** A few stable feature owners inside chat and provider construction.
- **Simplify:** Keep direct imports and the current ownership map.
- **Modularize:** Routing and result formatting when refactoring chat.
- **Refactor:** Central contracts incrementally, not via mass file churn.
- **Remove:** No application module proved dead.
- **Add:** Specific ownership tests as new boundaries appear.

### 3. Service boundaries

- **Well designed:** Query execution, metadata governance and external inference have distinct responsibilities.
- **Poorly designed:** Auth refresh can allocate a new query runtime; executor exposes validator machinery.
- **Over-engineered:** More deployable microservices would add cost for this load.
- **Under-engineered:** Bounded adoption and a documented SLM overload contract.
- **Simplify:** Keep one application; use explicit factories and finite admission.
- **Modularize:** Small application policies, not network services.
- **Refactor:** Findings 3 and 11.
- **Remove:** Cross-boundary construction from auth where practical.
- **Add:** A defined transition between published, prepared and request-ready resources.

### 4. Separation of concerns

- **Well designed:** Models never execute SQL; API delegates to use cases; bootstrap owns most allocation.
- **Poorly designed:** Chat contains demo vocabulary and presentation; transport understands SQLite.
- **Over-engineered:** Additional wrappers around pure functions would not help.
- **Under-engineered:** Error translation and shared provider endpoint policy.
- **Simplify:** Reuse existing contracts and small functions.
- **Modularize:** Existing routing/formatting responsibilities.
- **Refactor:** Findings 8, 11–13.
- **Remove:** Synthetic report tables from generic runtime policy after equivalent fixtures exist.
- **Add:** No framework or dependency container.

### 5. Dependency management

- **Well designed:** Lock files, optional Oracle/Redis dependencies and inward imports.
- **Poorly designed:** Full Settings and process environment are implicit adapter dependencies.
- **Over-engineered:** No new graph/vector packages justified.
- **Under-engineered:** Installed extension registration and native format/platform upgrade evidence.
- **Simplify:** Resolve typed configuration once per process.
- **Modularize:** Shared private endpoint/client policy.
- **Refactor:** Findings 10, 12 and 14.
- **Remove:** No additional runtime dependency demonstrated unnecessary.
- **Add:** Tests for the chosen native platform and adapter bootstrap.

### 6. Code structure

- **Well designed:** Explicit package roles, descriptive names, bounded typed operations.
- **Poorly designed:** ChatService, SQLValidator and metadata CLI are concentrated change hotspots.
- **Over-engineered:** File size alone does not justify more classes.
- **Under-engineered:** Focused routing/formatting ownership in the chat path.
- **Simplify:** Extract coherent jobs, not arbitrary groups of lines.
- **Modularize:** Independent SQL checks by operation only when extending that grammar.
- **Refactor:** Findings 11 and 16.
- **Remove:** No exact substantial function clones found by the static check.
- **Add:** Independent regression cases before moving risky logic.

### 7. Domain modeling

- **Well designed:** Certified metric IDs, grain, time, policy, physical precision and immutable catalog tuples.
- **Poorly designed:** Failure carries HTTP status; some defaults/compatibility rules encode synthetic banking assumptions.
- **Over-engineered:** Governance models are justified by signed approval requirements.
- **Under-engineered:** Clarification outcomes and persistent format versions.
- **Simplify:** Keep one typed reporting DSL rather than arbitrary model-generated SQL.
- **Modularize:** Catalog, plan and result contracts as they evolve.
- **Refactor:** Findings 1, 4, 8 and 13.
- **Remove:** Implicit business defaults from new restricted contracts where explicit certification is required.
- **Add:** A bounded planning clarification contract.

### 8. Layered architecture

- **Well designed:** No static import cycle or forbidden checked layer import found; native drivers stay outside domain/application.
- **Poorly designed:** Settings/telemetry are permitted shared dependencies with hidden environment/deadline behavior.
- **Over-engineered:** Protocols backed by real adapters and fakes generally earn their place.
- **Under-engineered:** Relative-import enforcement for future edits.
- **Simplify:** Prefer a pinned Catalog over unnecessary provider indirection in bundle-owned chat.
- **Modularize:** Keep composition in bootstrap and provider construction outside transport.
- **Refactor:** Findings 10, 11 and 13.
- **Remove:** SQL-driver awareness from HTTP error ownership gradually.
- **Add:** A test proving boundary enforcement catches relative violations.

### 9. API design

- **Well designed:** Stable EWS compatibility, typed API, owned sessions, bounded bodies and sanitized errors.
- **Poorly designed:** Shared chat behavior and telemetry are duplicated unevenly.
- **Over-engineered:** A replacement API framework or new frontend is unnecessary.
- **Under-engineered:** Explicit overload/wait semantics, whole-request cancellation and history pagination if required.
- **Simplify:** One invocation path with two response mappings.
- **Modularize:** Reusable route invocation helper, not a second application service hierarchy.
- **Refactor:** Finding 13.
- **Remove:** No preserved compatibility route without a deliberate deprecation decision.
- **Add:** Consistent failure/retry behavior and workload contract tests.

### 10. Business logic design

- **Well designed:** Metadata defines metrics; plans and SQL enforce approved semantics independently.
- **Poorly designed:** Exact English phrases and synthetic identifiers leak into generic routing.
- **Over-engineered:** A general-purpose agent planner would weaken this bounded reporting use case.
- **Under-engineered:** General clarification and controlled follow-up mutation.
- **Simplify:** Use existing catalog templates for exact reports.
- **Modularize:** Follow-up policy and exact financial formatting.
- **Refactor:** Findings 4, 5, 8 and 11.
- **Remove:** Broad keyword rejection that blocks ordinary read-only language.
- **Add:** Ambiguous-business-question and follow-up known-answer cases.

### 11. Data access patterns

- **Well designed:** Bound parameters, read-only transactions, pooled adapters, CAS session updates, transactional publication.
- **Poorly designed:** Persistence driver errors escape to HTTP; history contains full returned rows by design.
- **Over-engineered:** An ORM or server database migration is not justified for these local authority stores.
- **Under-engineered:** Schema evolution and aggregate resource preflight.
- **Simplify:** Retain small explicit repositories and separate discovery/query identities.
- **Modularize:** Existing repositories already provide the right boundary.
- **Refactor:** Findings 1, 2 and 13.
- **Remove:** No authority store or independent execution gate.
- **Add:** Upgrade/restore fixtures and realistic large-source workload cases.

### 12. State management

- **Well designed:** One request pins one bundle; leases drain retired resources; history has owner/version checks.
- **Poorly designed:** Process-local caches and pools multiply; registration and environment state are implicit.
- **Over-engineered:** A distributed event log or universal state manager is unnecessary.
- **Under-engineered:** Derived-state retention and serialized-state compatibility.
- **Simplify:** Keep policy/catalog/session authority durable and caches disposable.
- **Modularize:** Explicit process construction and bounded runtime adoption.
- **Refactor:** Findings 1–3, 7 and 14.
- **Remove:** Disk cache work from routine query encoding when not needed.
- **Add:** Controlled maintenance for old projections, respecting all active leases.

### 13. Error handling

- **Well designed:** Safe named failures, clear business clarification/unsupported results, generic external error messages.
- **Poorly designed:** HTTP status in the domain, SQLite handling in transport and incomplete pipeline failure events.
- **Over-engineered:** No need for dozens of exception subclasses or retry middleware.
- **Under-engineered:** Typed model abstention and consistent stage failure diagnostics.
- **Simplify:** Preserve stable codes and translate at the owning boundary.
- **Modularize:** Shared HTTP error mapping and application outcome handling.
- **Refactor:** Findings 4 and 13.
- **Remove:** No safety checks or redaction.
- **Add:** Safe failure-code/stage correlation without private content.

### 14. Configuration management

- **Well designed:** Validated values, SecretStr, explicit env selection, restricted provider gates.
- **Poorly designed:** Multiple loaders and similarly named independent budgets obscure effective configuration.
- **Over-engineered:** Another settings framework would worsen the problem.
- **Under-engineered:** An explicit resolved process configuration and truthful supported profiles.
- **Simplify:** Keep public env keys; pass resolved typed adapter settings.
- **Modularize:** Query, discovery, inference, retrieval and admission config ownership.
- **Refactor:** Findings 9, 10 and 14.
- **Remove:** The office launcher's mandatory embedding restriction.
- **Add:** Sanitized effective-budget diagnostics and precedence tests.

### 15. Extensibility

- **Well designed:** Provider ports, signed metadata metrics/templates and separate compiler/executor targets.
- **Poorly designed:** Local factory registration is not a complete stock CLI integration; new operators span several files.
- **Over-engineered:** General plugin discovery or arbitrary Python/SQL extensions are unnecessary.
- **Under-engineered:** Explicit process registration and version compatibility for approved extensions.
- **Simplify:** Use the existing private HTTP boundary for swappable qualified models.
- **Modularize:** Operator-specific checks as new supported operators are added.
- **Refactor:** Findings 1, 11 and 14.
- **Remove:** No extension seam solely because it has a single current implementation.
- **Add:** One real approved integration at a time, with contract tests.

### 16. Maintainability

- **Well designed:** Ownership documentation, strong local tools and meaningful safety/lifecycle tests.
- **Poorly designed:** Central contracts, orchestration hotspots and historical documentation can drift together.
- **Over-engineered:** Maintaining multiple alternative production stacks would add avoidable work.
- **Under-engineered:** Upgrade compatibility and long-term stored-state housekeeping.
- **Simplify:** One recommended operating profile and one current evidence register.
- **Modularize:** Only distinct responsibilities, not every step.
- **Refactor:** Findings 1, 8, 10, 11 and 16.
- **Remove:** Stale completion/test-count claims when editing current guides; retain historical reference as historical.
- **Add:** Previous-release fixtures and explicit change ownership.

### 17. Testability

- **Well designed:** Injected providers/pools, real embedded-engine tests, compiler mutations and lifecycle races.
- **Poorly designed:** Global registries/environment complicate isolation; direct service load bypasses transport and SLM work.
- **Over-engineered:** No need for a new testing framework or tests mirroring trivial wrappers.
- **Under-engineered:** 20-identity HTTP workload, persistent upgrade tests and chosen-model evidence.
- **Simplify:** Reuse existing harnesses and synthetic fixtures.
- **Modularize:** Provider construction seams, not test-only production abstractions.
- **Refactor:** Findings 6, 10 and 14.
- **Remove:** No meaningful safety or independent golden tests.
- **Add:** Upgrade, slow-provider, clarification, flexible-follow-up and deployment-target cases.

### 18. Reusability

- **Well designed:** Typed plans, adapters, catalog metadata and compilation logic are reusable across clients.
- **Poorly designed:** Banking phrases and full planning-adapter reuse leak into unrelated consumers.
- **Over-engineered:** A reusable enterprise framework is not the product.
- **Under-engineered:** Small shared HTTP policy and formatting/routing functions.
- **Simplify:** Extract the actual shared behavior at its owning level.
- **Modularize:** Finding 12's endpoint/client helpers.
- **Refactor:** Findings 8, 11 and 12.
- **Remove:** Cross-domain assumptions from generic functions.
- **Add:** No generic repository hierarchy, service locator or orchestration framework.

### 19. Scalability of application design

- **Well designed:** Bounded output/work inputs, shared admission option, immutable publications and separate inference endpoint.
- **Poorly designed:** Resource copies grow by grant partitions, workers and overlapping bundles; adoption waits are not fully budgeted.
- **Over-engineered:** Multi-host storage, sharding and distributed queues are not justified by 20 users.
- **Under-engineered:** Actual SLM saturation behavior and aggregate startup/adoption budgets.
- **Simplify:** Start qualification with one worker and finite active chats; add workers only with measured benefit.
- **Modularize:** Keep inference resource ownership separate from API process count.
- **Refactor:** Findings 2, 3, 6 and 7.
- **Remove:** Any assumption that more workers or Redis creates more inference capacity.
- **Add:** A measured concurrency/overload contract, not a promise of 20 parallel generations.

Large business-data volume remains Oracle's responsibility. A 1,000-row output limit does not bound how many rows Oracle scans or aggregates. Current design uses operator/join/output/time limits; it has no automatic small/medium/large cost classifier, general query decomposition or large-query job workflow. Add these only for a demonstrated supported workload, with DBA-approved resource policy.

### 20. AI/RAG architecture

- **Well designed:** Authorized metadata retrieval, typed planning, full-payload runtime token counting, output reserve, deterministic execution.
- **Poorly designed:** No typed model clarification, general prior-plan context or demonstrated real embedding benefit; schema text is repeated in default mode.
- **Over-engineered:** Agents, arbitrary SQL repair and another vector database are unnecessary.
- **Under-engineered:** Intent ambiguity, conversation transitions and selected-SLM evaluation.
- **Simplify:** Exact/BM25 baseline; optional measured hybrid retrieval; one compact typed plan call.
- **Modularize:** Typed planning input/outcome contracts and provider-specific formatting.
- **Refactor:** Findings 4, 5, 7, 9 and 15.
- **Remove:** Redundant prompt contract text only after mode-specific token/accuracy tests.
- **Add:** Held-out business questions, ambiguity/follow-up cases and paired lexical/hybrid evaluation on the same SLM.

## SOLID, clean architecture and duplication assessment

- **Single responsibility:** Mostly good at package level; weaker in ChatService and CLI composition. Extract routing/formatting, not a dozen tiny services.
- **Open/closed:** Models and executors have useful ports. New metrics using supported semantics are metadata work. A genuinely new SQL operator must change the DSL, plan checks, compiler, independent validator and tests; this deliberate coordination is safer than an unrestricted plugin hook.
- **Liskov substitution:** No concrete subtype violation was established. The object-identity catalog check and environment-dependent factories create extra assumptions future adapters must understand; make those contracts explicit or simplify them.
- **Interface segregation:** The execution port carries validation, readiness, entity resolution and lifecycle responsibilities. Exposing the concrete validator is avoidable coupling. Do not split every method into its own protocol without an actual consumer need.
- **Dependency inversion:** Checked import direction is sound. Shared settings/environment state, auth-triggered runtime adoption and planning transport reuse are the main hidden dependencies. Calling this entire codebase a clean-architecture violation would be inaccurate.
- **Duplication:** No substantial identical AST function body was detected. Compiler and independent validator intentionally restate important contracts. Do not merge those checks merely to remove duplication: shared wrong assumptions can defeat independent verification. The duplicated route invocation and provider client policy are better consolidation targets.
- **God modules:** ChatService, SQLValidator, `cli/metadata.py` and `domain/models.py` are likely maintenance hotspots, not automatically defective because of size. Their concrete change responsibilities matter more than an arbitrary line threshold.

## Ability to grow

| Growth dimension | Assessment |
|---|---|
| New metrics/tables within supported semantics | Good, through reviewed catalog/discovery/publication; automatic discovery does not certify meaning |
| Additional model endpoints | Good HTTP seam; each runtime's tokenizer/output schema behavior still needs qualification |
| A concrete installed local model/encoder | Integration work remains; path configuration alone is insufficient |
| Additional business databases | Possible, but not drop-in: discovery, physical mappings, SQL dialect, binds, context and executor tests must be implemented |
| More metadata | Bounded today; fix text accounting and measure partition/bundle memory before raising limits |
| More business rows | Mainly Oracle workload; output bounds do not guarantee bounded scan cost |
| Twenty users | Plausible architectural target; current office profile admits one active chat and has no waiting queue |
| Twenty simultaneous model generations | Not established; a model/hardware capacity requirement, not an API worker setting |
| Multiple developers | Clear package ownership helps; central chat/contracts/configuration files need coordinated changes |
| Multiple machines / high availability | Current local SQLite and embedded-resource design is not a qualified multi-host deployment architecture |
| Long-term maintenance | Reasonable foundation once persistent version evolution and release compatibility are explicit |

## Simplest recommended target

Keep a modular FastAPI application with three logical feature owners: reporting, conversations and metadata lifecycle. Keep pure contracts and application use cases, explicit bootstrap wiring and typed adapters. Retain SQLite authority, FTS5/BM25 retrieval, Ladybug projections and Oracle business execution.

Start qualification with **one API worker**, one configured SLM endpoint, the existing separate metadata monitor, and a conservative active-chat limit. Test 1, 2 and 4 active flexible questions, then higher only if results support it. These are test steps, not a capacity recommendation. Twenty users must be represented by distinct authorized identities in the workload.

Use Redis when multiple API workers need shared admission. Redis does not make the model faster, remove SQLite write serialization or replace current grants. If the selected operating contract requires automatic waiting, implement a small bounded wait with a deadline; do not silently queue unlimited requests or add a distributed jobs platform by default.

Keep embedding support available. Compare lexical and hybrid modes using the same model and held-out questions before choosing the default. Keep automatic graph/search/vector preparation for enabled approved components. Preserve review and signature requirements; ordinary schema discovery must never silently approve a new metric or permission.

## Refactoring order

1. Write workload/overload and upgrade acceptance cases; implement findings 1 and 2 without changing query semantics.
2. Make configuration and request/adoption budgets explicit; repair the encoder persistence hot path.
3. Add typed clarification and authorized previous-plan context; correct the demonstrated keyword false rejection.
4. Enable the supported lexical-only launcher profile, with compatible reviewed publications.
5. Extract routing/formatting and shared HTTP policy; unify route invocation/error ownership incrementally.
6. Qualify the selected SLM, actual catalog and approved Oracle against the 20-user workload. Optimize context or increase worker counts only from that evidence.

Do not combine all these changes into one rewrite. Keep compiler/validator goldens, access checks, exact Decimal handling, immutable publication identity and resource draining intact at each step.

## Chief architect's answer

**I would approve this architectural direction and continued controlled development. I would not approve this exact working tree for unrestricted production and years of maintenance yet.**

The reason is not the number of databases or a missing fashionable framework. The foundation is appropriately conservative for governed financial reporting. The remaining problems are explicit software-design gaps: persistent upgrades, complete resource bounds, bounded resource adoption, model clarification/conversation contracts and realistic workload evidence. They can be resolved while retaining the existing architecture.

Lean: **0 new runtime dependencies recommended; no major store removal justified.** Potential line savings from the proposed extractions/consolidation were not estimated.

Not checked: company Oracle, corporate identity, a real SLM/encoder, target VM/macOS capacity, full browser integration, penetration testing or every line of every test/asset. Native graph tests ran on this Windows machine; synthetic success does not establish office accuracy or capacity.

Verdict: **Keep the architecture, fix the concrete boundaries above, and qualify the 20-user SLM workload before production approval.**
