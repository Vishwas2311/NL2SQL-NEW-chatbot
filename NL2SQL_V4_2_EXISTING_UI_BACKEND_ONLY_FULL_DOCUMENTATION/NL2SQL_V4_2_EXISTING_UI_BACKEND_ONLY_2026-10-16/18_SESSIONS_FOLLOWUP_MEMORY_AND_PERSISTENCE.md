# 18 — Conversation Session Model, Context Carry-Forward and Retention

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Draft for review; no implementation or company production validation performed.  
**Document owner:** Backend + product + security  
**Gate:** P0  
**Baseline reference:** V4 research/blueprint supplied on 2026-10-15.  
**Data policy:** Fictional examples only; actual company schema and customer data stay in approved office systems.

> **Core distinction:** this document specifies future behavior. It does not claim that these modules, controls, model benchmarks, or Oracle permissions are already deployed.

## Design specification

## Session data design
Store `Session {id,principal_id,created_at,updated_at,policy_version,title,state}` and `Message {id,session_id,role,content_type,redaction_status,timestamp,query_ref}` with permitted retention. Store small `ContextSlots` {metric IDs, business entity IDs, approved filters, period, grouping, last catalog version, pending clarification}. Do not use full raw previous conversations by default as model context.

## Follow-up resolution rules
A follow-up edits only named dimensions from the prior authorized plan. Example: “and last year?” retains metric/grouping but alters period only when the prior state unambiguously exists. If user switches entity, domain or reporting unit, invalidate dependent joins/metric assumptions. Rerun catalog, permission and policy validation on **every** turn.

## Persistence and isolation
Session owner is the verified principal, not any request body identifier. Production persistence uses an approved durable store and separate write identity. SQLite is a development-only default. Use optimistic versioning or transactional writes to handle two concurrent tabs, and guard against duplicate client retries using idempotency keys. Support deletion/retention purge and employee offboarding requirements.

## Compaction
Summarize or slot-extract only deterministic approved context fields. An SLM-generated session summary can be displayed as text but must not be treated as a permission or certified metric source. Keep a safe limit on the number of turns and context token budget.

## Attack scenarios
Cross-user session ID tampering, forged previous query reference, stale/expired permissions, old catalog version, malicious assistant text in history, resumed clarification with inconsistent values, replay of cancelled query. Tests must prove fresh authorization and no data leakage.



## V4.1 sessions, reauthorization and semantic-view versions
Store the prior *approved business query slots* (metric ID, dimension IDs, period, filter tokens, view version) rather than an unlimited raw schema prompt. Every follow-up rechecks current entitlements and resolves catalog/view version changes; stale value-resolution tokens are discarded. A request to 'use the same view but last quarter' must reapply all mandatory filters and temporal rules. Session eviction/TTL and encryption are enterprise policy decisions; do not assume an indefinite retention period.
Sessions may remember a previous query as a conversational reference but must not cache another principal's result or validator capability. Audit lineage is separate from exposed session content.

---

## Deliverables / artifacts to review

Session schema, context-slot protocol, retention policy, ownership checks, multi-turn tests

## Acceptance tests and exit criteria

New/continue/delete sessions, cross-user ID denied, stale context revalidated, duplicate retry idempotent

## Open decisions and evidence required

Data retention and delete policy? Employee turnover? Maximum conversation length?

## Related documents

[02](./02_USER_JOURNEYS_AND_INTENTS.md), [09](./09_ROUTING_CONFIDENCE_AND_EXECUTION_PATHS.md), [10](./10_QUERY_PLAN_DSL_AND_VALIDATION.md), [16](./16_API_AUTH_AND_ERROR_CONTRACTS.md), [17](./17_FRONTEND_UX_RESULT_TABLES_AND_ACCESSIBILITY.md), [21](./21_SECURITY_PRIVACY_THREAT_MODEL.md)


---

## Clarification and follow-up examples
- Previous: “Show monthly net sales in 2025.” Follow-up: “Make that 2024.” Preserve metric/dimension, replace period only after checking catalog and permissions.
- Previous: “Show top customers by exposure.” Follow-up: “Which ones were inactive?” Resolve inactive definition and any required additional sources; do not simply append text to previous SQL.
- Previous: “Show balance for customer A.” Follow-up: “Show customer B.” Resolve B under current user's permissions; do not preserve A's bind value.

### Session write atomicity
Create the user message and generated result as separately status-tracked events so a server crash does not mislabel an unexecuted query as successful. Use a uniqueness constraint on `(principal, client_request_id)` for idempotent chat submit, where feasible. Persist approved semantic slots only after authoritative validation, not after an unverified SLM draft.

### Retention edge cases
Authenticated account disabled during a long conversation; next turn denied. Metric definition changed between turns; discard or re-ground stale slots. Session shared accidentally by URL; server returns generic not-found to another principal. Deletion purges or tombstones records per approved retention and audit rules rather than promising immediate erasure of required security logs.

---

## Session-context reducer and race conditions
The context reducer should derive authorized state from the last validated plan and result metadata, **not** arbitrarily summarize all conversational prose. Use a `ContextPatch` operation to modify selected slots (e.g., `reporting_period`). Unknown follow-up references should ask clarification. A change to entity scope can require re-resolving filter values and joins.

### Concurrent-tab scenario
Tab A requests 2025 sales, tab B requests 2024 sales in the same session. Both must carry message ordering and expected session version. A stale writer should not silently overwrite newer plan context. Use optimistic concurrency with conflict/rebase or reject safely. Idempotent client IDs prevent repeat network submits from doubling session events or Oracle work.

### Stored session data schema
```json
{
 "session_id":"synthetic-s1",
 "principal_id":"server-owned-principal",
 "last_catalog_version":"demo-v1",
 "last_validated_query_plan_ref":"plan-103",
 "context_slots":{"metric_ids":["net_sales"],"period":"2025","group_by":["region"]},
 "pending_clarification":null
}
```
Never trust a client-submitted copy of this state for authorization; the backend loads it from owned storage. Enforce retention, secure deletion and legal hold according to a separate approved policy.

### Multi-turn regression cases
Time-only follow-up; swap metric; swap customer entity; ask for a disallowed field; previous query executed under permission now revoked; previous catalog version retired; incomplete clarification after session expiry; concurrent requests reorder messages. Each case has an explicit expected safe outcome.

---


## V4.2 EWS session integration boundary
The existing UI drives creation of a new conversation by locally clearing `currentSessionId` and sends `session_id: null` with the first `/ews-chatbot/chat` message. The backend creates and returns the server-owned session. Implement `/ews-chatbot/get_all_sessions` and `/ews-chatbot/load_session/{id}` compatibility mappings; server-side authorization always supersedes `user_id` submitted by the browser. Session delete remains a backend capability but the supplied UI has no delete control; do not build one before a separately approved UI integration change. See [35](./35_EXISTING_UI_INTEGRATION_CONTRACT.md).

---

## Historical V4 Baseline Requirements (reference only; superseded where V4.1 refines them)

> **Historical UI exclusion:** Any older requirement below to create a React/TypeScript/Vite frontend, new browser pages, screens, or UI build/test pipeline is superseded by the user decision. These are historical notes, **not implementation tasks**. Preserve existing capabilities for later integration via document 35.

> This is preserved from the earlier planning draft for comparison. The current V4.1 design section, companion docs 30–34, the approved ADR register, and subsequent validated contracts take precedence on changes explicitly addressed in the V4.1 refinement. Historical descriptions of optional vector providers, open SQL fallback, and late Oracle tests are **not** new mandatory decisions.


The following material records relevant requirements from the previously agreed V4 blueprint. The sections above are the detailed module design and take precedence where they add stricter controls. Original V4 is a **proposed architecture**, not independently verified production source.

# 17. Conversation Memory and Session Management

## 17.1 What we need

Users should be able to ask follow-up questions.

Example:

Question 1: "Show total exposure for 2025."

Question 2: "Now compare it with 2024."

The system should understand the second question in the context of the first.

## 17.2 Conversation state

Store:

- Session ID.
- Authenticated user ID.
- Message IDs.
- Timestamps.
- User messages.
- Assistant responses.
- Query references.
- Safe semantic-plan references.
- Catalog version.
- Clarification state.
- Relevant conversation context.

## 17.3 Efficient conversational memory

Do not send every previous message to Gemma.

Prefer a compact state containing:

- Current business intent.
- Selected metrics.
- Relevant entities.
- Current filters.
- Reporting period.
- Last approved query-plan reference.
- Unresolved clarifications.

## 17.4 Security of follow-up questions

Revalidate permissions and metadata for each new request.

A previous query's approval does not automatically authorize a later query.

## 17.5 Storage

Local development can use SQLite.

Production should use an approved durable session store, potentially the existing enterprise session database.

Separate session persistence from read-only business query execution.

---
