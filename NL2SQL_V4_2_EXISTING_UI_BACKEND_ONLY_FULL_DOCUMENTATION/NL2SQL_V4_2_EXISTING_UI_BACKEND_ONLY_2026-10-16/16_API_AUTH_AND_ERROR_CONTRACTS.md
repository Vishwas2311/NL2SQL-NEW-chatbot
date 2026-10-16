# 16 — Versioned API, Authentication, Authorization and Error Contracts

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Draft for review; no implementation or company production validation performed.  
**Document owner:** Backend + security + frontend  
**Gate:** P0  
**Baseline reference:** V4 research/blueprint supplied on 2026-10-15.  
**Data policy:** Fictional examples only; actual company schema and customer data stay in approved office systems.

> **Core distinction:** this document specifies future behavior. It does not claim that these modules, controls, model benchmarks, or Oracle permissions are already deployed.

## Design specification

## Public contract strategy
Maintain typed internal `/api/v1` endpoints as needed for backend consumers, and **require** an `/ews-chatbot/*` compatibility router for the supplied EWS client at integration time. Do not require UI rewrites. See document 35 for exact observed paths, payloads and response fields. Do not allow a client-supplied `user_id`, SQL text, table list or model choice to grant access. User and tenant identity derive from verified authentication token/session.

## Routes and semantics
| Method | Path | Contract |
|---|---|---|
| POST | `/api/v1/chat` | `{session_id?, message, client_request_id?}` -> typed ChatResult |
| POST | `/api/v1/sessions` | Create user-owned session |
| GET | `/api/v1/sessions` | Paginated owned sessions |
| GET | `/api/v1/sessions/{id}` | Session with authorized messages |
| DELETE | `/api/v1/sessions/{id}` | Delete/expire owned session according to retention |
| POST | `/api/v1/queries/{id}/cancel` | Idempotent cancellation when running |
| POST | `/api/v1/feedback` | Non-sensitive correctness feedback |
| GET | `/api/v1/health/live` | Process status, no private internals |
| GET | `/api/v1/health/ready` | Dependencies appropriate to role |

## Chat response discriminated union
`completed` includes result type, typed columns/rows, applied period/units, provenance summary, truncation and query reference. `clarification_required` includes safe options/reason. `unsupported`, `denied`, `timeout`, `service_unavailable`, `failed` include stable error codes. Do not force frontend to parse raw SQL or untrusted HTML. Use pagination tokens bound to principal and result state; expire on catalog/policy change.

## HTTP error behavior
400 malformed JSON; 401 unauthenticated; 403 denied; 404 missing owned resource without existence leak; 409 stale catalog/session conflict; 413 oversized user input; 422 invalid typed fields; 429 rate limited; 503 required dependency unavailable; 504 query deadline exceeded. Not every unsupported business question needs an HTTP error: an explicit typed clarification/unsupported result can use 200 when appropriate.

## Security and resiliency
Validate JWT issuer, audience, signature, expiry and key rotation; map corporate entitlements to signed server-side principal. Enforce per-user and global request limits; correlation ID and idempotency for duplicate client retries; CSRF for cookie auth; CORS restricted to approved origins; sanitization for any user-supplied Markdown.

## Contract testing
Generate OpenAPI/schema fixtures; pin response versions. Test all states, expired auth, cross-owner sessions, malicious JSON injection, streaming/pagination cancellation, stale catalog and maintenance errors. The frontend/backend interface must remain stable while internal model/retrieval components change.



## V4.1 contract extensions and compatibility behavior
Add a versioned typed `ResponseMeta` to completed responses: `semantic_view_id` (only when safe to expose), `metric_display_name`, `reporting_period`, `freshness_status` (`verified`, `unknown`, `stale`, `not_applicable`), `result_truncated`, `query_reference`, and explanation of clarification/unsupported outcomes. Preserve user-facing compatibility via an EWS adapter as the **required integration surface**; the supplied existing UI is the only UI (17, 35). Internal path-specific details (retrieval scores, physical schema, auth grants) must not leak through API errors.
An operation-specific fallback failure maps to safe `unsupported_query` or `clarification_required`, not success with a fabricated answer. API request IDs correlate authorization, catalog version, preflight and result records. See [27](./27_TYPED_CONTRACTS_ERRORS_AND_END_TO_END_EXAMPLE.md).

---

## Deliverables / artifacts to review

OpenAPI v1, typed ChatResult/error models, auth policy, compatibility requirements and contract tests

## Acceptance tests and exit criteria

Every endpoint has auth/ownership tests and error examples; no identity injection; no unvalidated HTML

## Open decisions and evidence required

Corporate SSO protocol? Existing UI is fixed. Decide how to securely provide credentials/session identity, whether STT is enabled, and whether the UI can support streaming; synchronous JSON is its current contract.

## Related documents

[01](./01_SCOPE_PRD_AND_NFR.md), [02](./02_USER_JOURNEYS_AND_INTENTS.md), [09](./09_ROUTING_CONFIDENCE_AND_EXECUTION_PATHS.md), [17](./17_FRONTEND_UX_RESULT_TABLES_AND_ACCESSIBILITY.md), [18](./18_SESSIONS_FOLLOWUP_MEMORY_AND_PERSISTENCE.md), [19](./19_RESULT_PROVENANCE_FRESHNESS_AND_EXPLANATIONS.md), [21](./21_SECURITY_PRIVACY_THREAT_MODEL.md)


---

## Public API payload examples
```json
{"session_id":"demo-s1","message":"Net sales by region for 2025","client_request_id":"demo-r1"}
```
```json
{"status":"clarification_required","session_id":"demo-s1","message_id":"demo-m1","clarification":{"reason":"MULTIPLE_METRIC_MATCHES","question":"Which approved sales metric do you mean?","options":[{"id":"gross_sales","label":"Gross sales"},{"id":"net_sales","label":"Net sales"}]}}
```
The listed options must already be authorized for this user. Do not include internal SQL, actual customer names or unauthorized metric labels.

### Idempotency and retry behavior
`client_request_id` deduplicates accidental duplicate request submission within an authenticated session for a configured period; it cannot be used to replay another principal's result. Result pagination cursor is cryptographically bound to user scope, query ID, catalog digest and expiry. Retries after 503 must not cause two SQL jobs to execute in parallel without coordination.

### API contract negative tests
Tamper with `session_id`, propose a different `user_id`, use unauthorized source fields in JSON, request an arbitrary SQL string, exceed input size, send invalid JSON UTF-8, abuse pagination and cancel another user's query. Each must return a consistent safe HTTP status without DB execution.

---

## Historical V4 Baseline Requirements (reference only; superseded where V4.1 refines them)

> **Historical UI exclusion:** Any older requirement below to create a React/TypeScript/Vite frontend, new browser pages, screens, or UI build/test pipeline is superseded by the user decision. These are historical notes, **not implementation tasks**. Preserve existing capabilities for later integration via document 35.

> This is preserved from the earlier planning draft for comparison. The current V4.1 design section, companion docs 30–34, the approved ADR register, and subsequent validated contracts take precedence on changes explicitly addressed in the V4.1 refinement. Historical descriptions of optional vector providers, open SQL fallback, and late Oracle tests are **not** new mandatory decisions.


The following material records relevant requirements from the previously agreed V4 blueprint. The sections above are the detailed module design and take precedence where they add stricter controls. Original V4 is a **proposed architecture**, not independently verified production source.

# 16. Backend API Design

Use FastAPI with versioned public endpoints for the new application.

## 16.1 Core API endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/health/live` | GET | Process liveness |
| `/api/v1/health/ready` | GET | Dependency readiness |
| `/api/v1/chat` | POST | Submit natural language query |
| `/api/v1/sessions` | POST | Create chat session |
| `/api/v1/sessions` | GET | List owned sessions |
| `/api/v1/sessions/{id}` | GET | Load session |
| `/api/v1/sessions/{id}` | DELETE | Delete owned session |
| `/api/v1/sessions/{id}/messages` | GET | Retrieve history |
| `/api/v1/feedback` | POST | Record feedback |
| `/api/v1/queries/{id}/cancel` | POST | Cancel a supported running query |
| `/api/v1/speech/transcriptions` | POST | Optional speech transcription |

Administration endpoints, if needed, should be separately authorized and isolated from ordinary users.

## 16.2 Chat request

Example:

```json
{
  "session_id": "optional-session-id",
  "message": "Show top ten customers by exposure",
  "client_request_id": "request-123"
}
```

The authenticated user identity must come from validated authentication credentials, not from a client-supplied `user_id`.

## 16.3 Chat response

Example:

```json
{
  "session_id": "session-123",
  "message_id": "message-456",
  "status": "completed",
  "response": "Here are the matching results.",
  "result": {
    "type": "table",
    "columns": ["customer", "exposure"],
    "rows": []
  },
  "query_reference": "query-789",
  "warnings": [],
  "requires_clarification": false
}
```

The exact public API schema should be versioned and tested.

## 16.4 Existing office compatibility

At the later UI integration milestone, the backend **MUST** expose an adapter preserving the supplied EWS UI routes and response fields; this is not optional.

The reported existing routes include:

- `/ews-chatbot/chat`
- `/ews-chatbot/get_all_sessions`
- `/ews-chatbot/load_session/{session_id}`
- `/ews-chatbot/delete_session/{session_id}`
- `/health`

Compatibility must be verified against the **three uploaded UI source files** plus approved office integration tests; reported historical office behavior is not considered verified beyond these files.

Do not force new frontend changes merely to accommodate internal backend restructuring.

---
