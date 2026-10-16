# 02 — User Journeys, Intent Types and Conversation UX

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Draft for review; no implementation or company production validation performed.  
**Document owner:** Product + UX + domain owner  
**Gate:** P0  
**Baseline reference:** V4 research/blueprint supplied on 2026-10-15.  
**Data policy:** Fictional examples only; actual company schema and customer data stay in approved office systems.

> **Core distinction:** this document specifies future behavior. It does not claim that these modules, controls, model benchmarks, or Oracle permissions are already deployed.

## Design specification

## Journey catalog
| ID | User journey | Expected system behavior |
|---|---|---|
| J-01 | Single-table lookup | Filter a certified view by authorized identifier, show result |
| J-02 | Top-N ranking | Resolve governed metric, sort, limit and units |
| J-03 | Historical comparison | Resolve fiscal period and as-of rules; no current-state leakage |
| J-04 | Follow-up with context | Carry forward metric, scope and filters; replace only specified dimension |
| J-05 | Ambiguous phrase | Offer the smallest business clarification before SQL generation |
| J-06 | Missing entity match | Explain unknown/ambiguous value safely; do not reveal hidden candidates |
| J-07 | Unsupported advanced calculation | Clarify or reject; never fabricate a formula |
| J-08 | Slow/large query | Inform user of limits; support cancellation and safe pagination |
| J-09 | Expired authorization | Require renewed session; discard stored execution rights |
| J-10 | Source data stale | Show explicit freshness/period warning |

## State machine
`received -> authenticated -> context_resolved -> grounded -> {clarification_required | planned | denied} -> {compiled | fallback_generated} -> validated -> executing -> {completed | empty | truncated | failed | cancelled}`.
Only `validated` is permitted to transition to `executing`. Each transition has a reason code, request ID and elapsed time. Clarification is a pause/resume state; resumed input must be reauthorized and reretrieved.

## Conversation rules
- Persist a typed last-plan reference and sanitized slots (metric ID, entity ID, period, dimensions, allowed predicates), not unrestricted latent assumptions.
- “What about last year?” preserves the previous metric and entity filters but changes the period. Reconfirm when history is missing or ambiguous.
- Do not silently infer a reporting year, currency, business-unit scope or high-risk threshold where the domain defines no default.
- Treat model-generated explanatory prose as untrusted; no result number should appear without an underlying executed result or approved deterministic text.

## UX copy standards
The interface must distinguish no matching records, unsupported metric, access denied, data stale, computation timed out, and clarification required. Avoid displaying internal stack traces, restricted object names or Oracle connection details. Result footers display reporting period, truncation, units and freshness where known.

## UI accessibility and degraded states
Keyboard-first chat input, visible loading/cancel state, table accessibility, screen-reader announcements for results, and reduced-motion support. Model offline should yield a service-unavailable state, not silent spinner. Saved certified templates may remain available only if the application can still enforce authorization and query policy.



## V4.1 user journeys for new architecture
| Journey | User experience | Backend requirement |
|---|---|---|
| Certified metric and view | Fast answer with reporting period, units and source freshness | 0-model path only after strict template/parameter verification |
| Flexible wording for known business view | Answer after compact SLM plan | Exact/BM25 first; vector only if warranted; typed plan/validation |
| Unknown name or account | Safe disambiguation without exposing denied entities | Scoped value resolver, never customer names in public vector indexes |
| Ambiguous reporting date | Clarification of as-of date vs run date | Semantic view time roles and catalog version |
| Unsupported analytic expression | Explain supported alternatives or clarify | Strict fallback operation allowlist; no SQL execution without complete validation |
| Enterprise engine down | Graceful service error, no fabricated result | Structured retry limits, session preserved, provider health |
| Historical conversation | Re-evaluate identity, rights, snapshot and requested metric | Typed follow-up slots; never reuse prior authorization |
User feedback should separate *wrong metric*, *wrong entity*, *wrong join*, *wrong numbers*, *stale data*, *unsupported query*, and *slow response* for evaluation.

---

## Deliverables / artifacts to review

Journey map, UX states, error and clarification copy matrix, multi-turn examples, definition of ready for UI

## Acceptance tests and exit criteria

Ten journey E2E tests and state transition invariants; screen-reader, keyboard and auth expiry checks

## Open decisions and evidence required

Are charts/export/speech in P0 or P1? Are there pre-approved fiscal calendars and default date ranges?

## Related documents

[01](./01_SCOPE_PRD_AND_NFR.md), [09](./09_ROUTING_CONFIDENCE_AND_EXECUTION_PATHS.md), [16](./16_API_AUTH_AND_ERROR_CONTRACTS.md), [17](./17_FRONTEND_UX_RESULT_TABLES_AND_ACCESSIBILITY.md), [18](./18_SESSIONS_FOLLOWUP_MEMORY_AND_PERSISTENCE.md)


---

## Historical V4 Baseline Requirements (reference only; superseded where V4.1 refines them)

> **Historical UI exclusion:** Any older requirement below to create a React/TypeScript/Vite frontend, new browser pages, screens, or UI build/test pipeline is superseded by the user decision. These are historical notes, **not implementation tasks**. Preserve existing capabilities for later integration via document 35.

> This is preserved from the earlier planning draft for comparison. The current V4.1 design section, companion docs 30–34, the approved ADR register, and subsequent validated contracts take precedence on changes explicitly addressed in the V4.1 refinement. Historical descriptions of optional vector providers, open SQL fallback, and late Oracle tests are **not** new mandatory decisions.


The following material records relevant requirements from the previously agreed V4 blueprint. The sections above are the detailed module design and take precedence where they add stricter controls. Original V4 is a **proposed architecture**, not independently verified production source.

# 8. Intent Router and Query Understanding

## 8.1 What the intent router does

The router identifies the type of user request before selecting a query strategy.

Supported categories:

| Intent | Example | Handling |
|---|---|---|
| Lookup | Show customer details | Filtered selection |
| Aggregation | Count high-risk customers | Approved aggregate |
| Ranking | Top ten accounts by exposure | Aggregate + sort + limit |
| Comparison | Compare this year with last year | Period-aware query |
| Trend | Monthly exposure trend | Time-series query |
| Historical | Risk status as of June | Effective-date logic |
| Multi-table | Customers with several indicators | Verified joins |
| Follow-up | What about last quarter? | Session-context resolution |
| Ambiguous | Show high exposure customers | Clarify undefined threshold |
| Unsupported | Request unavailable information | Explain limitation |
| Disallowed | Attempt to modify database records | Reject |

## 8.2 Routing without unnecessary SLM calls

A simple deterministic rule or validated intent template should be used when it is sufficient.

For more flexible questions, the router uses the SLM.

Avoid creating a separate SLM call solely for intent classification unless the evaluation proves that the extra call is beneficial.

For many requests, intent detection and structured query planning can happen in the same model call.

## 8.3 Clarification conditions

Ask for clarification when:

- Two metrics have different valid definitions.
- The requested time period is unclear.
- A requested dimension is not compatible with the metric.
- Multiple approved join paths yield different answers.
- A required customer or entity is unidentified.
- A business threshold is unspecified and no approved default exists.

Clarification is preferable to producing confident but incorrect SQL.

---

---

# 15. Chatbot Frontend

The supplied EWS browser UI is already built. The backend and compatible response behavior are in scope; no new frontend development is in scope. This section retains desired UX behaviors for later integration acceptance.

## 15.1 Recommended stack

**Existing HTML/CSS/JavaScript UI supplied by the user**

Do not create a new frontend framework or screens. Integrate the preserved assets at the authorized integration phase.

The project MUST supply a backend compatibility adapter for the uploaded EWS UI and its current API contract. See 35.

## 15.2 Main frontend features

| Feature | Description |
|---|---|
| Login | Company-approved authentication |
| Chat interface | Natural language input and conversation display |
| New conversation | Create a new independent chat |
| Session list | Display previous chats |
| Session loading | Restore conversation history |
| Follow-up questions | Continue a conversation |
| Response tables | Display Oracle query results |
| Charts | Optional presentation of suitable numeric results |
| Export | Controlled CSV/download functionality if authorized |
| Query details | Optional display of safe query metadata |
| Clarification UI | Ask users for missing business meaning |
| Status indicators | Processing, failed, completed, timed out |
| Error handling | Friendly messages without internal secrets |
| Accessibility | Keyboard support and readable states |
| Responsive design | Desktop and mobile-friendly layouts |
| Feedback | Allow users to flag incorrect results |
| Speech input | Optional approved speech-to-text integration |

## 15.3 Response rendering

The backend should return structured content rather than requiring the browser to parse arbitrary model-generated HTML.

Possible response types:

- Text.
- Table.
- Chart specification.
- Clarification question.
- Empty result.
- Error.
- Unsupported request.

Frontend rendering should safely escape ordinary text.

Never render arbitrary model-produced HTML without appropriate sanitization and policy.

## 15.4 Frontend security

- No embedded database credentials.
- No model-server secrets.
- No enterprise API keys.
- Secure authentication/session handling.
- Appropriate CSRF protection depending on authentication design.
- Strict content security policy.
- Authorized access to exported data.
- Safe handling of query results.

---

---

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

---

# 18. Result Processing and Answer Generation

## 18.1 Result formatting

The result processor must convert typed database output into user-friendly content.

Supported formats:

- Single values.
- Tables.
- Ranked lists.
- Time-series summaries.
- Comparisons.
- Simple charts.
- No-data explanations.

## 18.2 Do we need Gemma to explain results?

Not always.

For standard results, deterministic templates are sufficient.

Example:

"Ten matching customers were found for the selected period."

For complex interpretations, Gemma may generate a natural language summary from approved, minimized result data.

The generated summary must not invent facts or make unsupported business judgments.

## 18.3 Result quality checks

Verify:

- Expected columns are returned.
- Numeric values retain precision.
- Dates are formatted correctly.
- Units and currencies are clear.
- Truncation is disclosed.
- Empty results are not described as execution failures.
- Restricted values are not exposed.

## 18.4 Chart generation

Use deterministic chart specifications based on result types and approved presentation rules.

A language model should not invent chart data.

---
