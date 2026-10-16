# 22 — Private Deployment Topology, Model Infrastructure and Fulcrum Questions

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Draft for review; no implementation or company production validation performed.  
**Document owner:** Platform + infrastructure + DBA  
**Gate:** P0  
**Baseline reference:** V4 research/blueprint supplied on 2026-10-15.  
**Data policy:** Fictional examples only; actual company schema and customer data stay in approved office systems.

> **Core distinction:** this document specifies future behavior. It does not claim that these modules, controls, model benchmarks, or Oracle permissions are already deployed.

## Design specification

## Deployment modes
**Developer:** FastAPI backend + synthetic SQLite + immutable synthetic catalog + optional embedding + approved local model/mock. Preserve uploaded UI assets as integration references, but do not build or serve a new UI during backend development. **Integration:** approved company-hosted API, internal inference endpoint, test Oracle schema, durable session database and monitoring. **Production:** separately controlled app workers, inference serving where hardware requires, existing Oracle service, persistent metadata and sessions, private network and workload admission control.

## Container independence
The application should run natively on permitted OS using pinned Python env, native service manager and local files; Docker is optional where approved. A small in-memory graph requires no graph server. A vector service is not required for a lexical-first small catalog. Additional VM is determined by inference hardware, concurrency, isolation and storage needs—not by architectural fashion.

## Fulcrum discovery checklist
Confirm actual OS/VM ownership, user install permissions, Python/runtime constraints, approved process manager, writable persistent paths, storage quotas, CPU and GPU, memory, inference endpoint access, Oracle driver/client versions, DNS/TLS, private routing, SSO identity propagation, logging, backup and capacity. Source repository manifests only indicate *possible* services; they do not prove what runs on production Fulcrum.

## Artifact delivery
Publish pinned backend wheel/dependency lock, existing UI asset integration package (separate later-approved deployment), signed catalog snapshot and search index, model checkpoint identifier/hash (distributed by approved channel), runtime configuration template, service startup commands and health probes. Secrets never bundled in artifacts. Runtime enables only required modules.

## Capacity and resilience
Model inference queue length/worker count based on measured prefill/decode/KV memory; separate fast-path from GPU overload where policy allows; bounded Oracle connections; graceful cancellation/shutdown, restart behavior, readiness contracts and rolling/rollback release. Measure memory at concurrent load, not only model weight disk size.

## Company integration only
Real Oracle metadata import, schema grants, customer aliases and approved query evaluation remain inside organization. Portable package uses synthetic abstractions. If a central managed inference server is not provisioned, reduce rollout concurrency or stage launch; don't assume CPU-only VM delivers acceptable 12B production latency.



## V4.1 deployment topology and data-boundary decisions
Local development: one FastAPI process (catalog, SQLite FTS5/BM25, NetworkX, compiler, validator), mock EWS API client / contract tests, fictional SQLite dataset, optional local FAISS index, and a mock/approved Gemma runtime. Production: application process may run on an approved VM; SLM endpoint may need a separate internal GPU service; Oracle stays on owned DB infrastructure; persistent sessions/catalog snapshots reside on approved durable storage. **No mandatory Neo4j/Milvus/Qdrant/Graphify service.**
Physical Oracle views are optional and DBA-controlled; logical semantic views live in approved catalog and compile to Oracle-safe SQL. Before platform signoff verify storage/persistence, model weights/licenses, network egress, internal TLS, model capacity and Oracle version. This package does **not** establish that Fulcrum can host inference or connect to Oracle. Deployment ADRs are in 28; qualifications in 33.

---

## Deliverables / artifacts to review

Deployment diagrams and topology options, resource questionnaire, IaC/config inventory, run/rollback runbook

## Acceptance tests and exit criteria

Cold/restart readiness, zero internet inference egress, catalog persistence, resource admission and test Oracle access

## Open decisions and evidence required

Where will the SLM run? What machine/network rights does Fulcrum have? Persistent storage and VM GPU?

## Related documents

[03](./03_SYSTEM_ARCHITECTURE_AND_RUNTIME.md), [11](./11_LOCAL_SLM_MODEL_CONTEXT_AND_RUNTIME.md), [15](./15_ORACLE_ADAPTER_PREFLIGHT_AND_RESOURCES.md), [20](./20_CACHING_LATENCY_AND_RESOURCE_BUDGETS.md), [21](./21_SECURITY_PRIVACY_THREAT_MODEL.md), [23](./23_OBSERVABILITY_SRE_AND_OPERATIONS.md), [25](./25_IMPLEMENTATION_ROADMAP_DEPENDENCIES_AND_GATES.md)


---

## Deployment dependency table
| Component | Startup readiness | Persistence | Hardware bottleneck |
|---|---|---|---|
| FastAPI services | Catalog/auth/config healthy | Minimal | CPU/worker count |
| Metadata snapshot | Verified signature + catalog hash | Required | Low |
| In-memory join graph | Loaded from approved snapshot | Rebuildable | Low at small scale |
| Optional embedding index | Index/model digest match | Rebuildable | Memory/storage |
| Model server | Checkpoint/runtime and health ready | Weights stored | GPU/VRAM/CPU/KV |
| Oracle connection pool | Query identity grants and network ready | External Oracle | DB capacity/connections |
| Session store | User ownership/persistence verified | Required | DB/IO availability |

### Startup and rollback detail
On restart, load last approved immutable catalog, validate index digest, initialize graph, check database driver and model service. If catalog validation fails, *do not* offer query execution. Rolling deployment versions must negotiate API and catalog schema compatibility. Releasing a new model alone must not change certified business definitions. Prepared rollback includes previous code build, catalog pointer and model checkpoint, with no uncontrolled schema writes.

---

## Historical V4 Baseline Requirements (reference only; superseded where V4.1 refines them)

> **Historical UI exclusion:** Any older requirement below to create a React/TypeScript/Vite frontend, new browser pages, screens, or UI build/test pipeline is superseded by the user decision. These are historical notes, **not implementation tasks**. Preserve existing capabilities for later integration via document 35.

> This is preserved from the earlier planning draft for comparison. The current V4.1 design section, companion docs 30–34, the approved ADR register, and subsequent validated contracts take precedence on changes explicitly addressed in the V4.1 refinement. Historical descriptions of optional vector providers, open SQL fallback, and late Oracle tests are **not** new mandatory decisions.


The following material records relevant requirements from the previously agreed V4 blueprint. The sections above are the detailed module design and take precedence where they add stricter controls. Original V4 is a **proposed architecture**, not independently verified production source.

# 21. Local SLM Hosting and Production Infrastructure

## 21.1 Development deployment

For an Apple Silicon development machine, an MLX-compatible runtime is a reasonable starting point if it supports the selected model correctly.

Requirements:

- Local model files.
- Approved model license and distribution.
- Configurable quantization.
- Structured-output compatibility checks.
- HTTP or in-process adapter.
- Token/memory instrumentation.
- Model-loading and inference health checks.

## 21.2 Production deployment

The production deployment may use:

**Application server**

Hosts FastAPI, semantic catalog, retrieval, graph, compiler and validation services.

**Inference server**

Hosts the approved SLM runtime and model weights.

**Oracle database**

Hosts approved business data and potentially separately permissioned application persistence.

The application and model may share a server if resources permit.

A separate model server is advisable when inference hardware requirements, concurrency or scaling justify it.

## 21.3 Production model-serving options

Evaluate approved runtimes such as:

- vLLM.
- SGLang.
- Other compatible internal serving systems.

Selection criteria:

- Model compatibility.
- Structured output.
- Quantization support.
- GPU requirements.
- Concurrent inference.
- Memory footprint.
- Security and operational fit.
- Performance under representative requests.

## 21.4 Fulcrum deployment considerations

Before deploying on Fulcrum or another enterprise VM, confirm:

- Available CPU and GPU.
- RAM and model memory requirements.
- Supported operating system.
- Installation restrictions.
- Persistent storage availability.
- Model artifact storage.
- Network access to Oracle.
- Network access to the inference endpoint.
- Service startup and restart permissions.
- Monitoring integration.
- Concurrency and availability requirements.

Do not assume an ordinary application VM can efficiently serve a 12B model.

## 21.5 No mandatory Docker requirement

The initial architecture should support native Python deployment.

Docker can be used where authorized, but it must not be required for local metadata storage, an in-memory graph or basic retrieval.

## 21.6 Reliability

Implement:

- Readiness and liveness checks.
- Graceful shutdown.
- Connection pool cleanup.
- Model-service timeout handling.
- Retry policies for transient infrastructure failures.
- Request cancellation.
- Concurrency controls.
- Deployment rollback.
- Version-pinned artifacts.

---
