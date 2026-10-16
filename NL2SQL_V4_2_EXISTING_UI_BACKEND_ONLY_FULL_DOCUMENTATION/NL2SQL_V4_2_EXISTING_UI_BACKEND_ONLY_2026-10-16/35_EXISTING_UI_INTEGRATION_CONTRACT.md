# 35 — Existing EWS UI: Immutable Asset Contract and Deferred Backend Integration

**Status:** Binding product UI selection; **no browser-to-new-backend integration has occurred**.  
**Date:** 2026-10-16.  
**Owner:** Backend/API + security + UI asset owner.  
**References:** Three files supplied by the user: `index(1).html`, `script(3).js`, `style(3).css`. Exact-byte copies (renamed to canonical referenced names) are packaged under `existing_ui_reference/` for contract verification.

## 1. Explicit user requirement / scope change
The EWS Conversation AI UI already exists and is the **only UI to use**. **Build the NL-to-SQL backend only**. Do not create React, TypeScript, Vite, a replacement HTML page, redesigned chat components, new CSS, mock frontend pages, or a frontend build pipeline. Do not modify or integrate these UI files during the current backend-building phases. Preserve every other V4.1 capability, including business semantic views, lexical-first retrieval, optional FAISS, NetworkX verified join graph, Gemma structured planning, SQL compiler, guards, Oracle, sessions, results, metrics, performance and deployment planning.

Later, and **only with explicit approval**, connect the existing UI to a compatibility API and address security/hosting constraints with minimal agreed UI edits if necessary; never silently replace the user design.

## 2. File inventory and provenance
| Uploaded file | Packaged reference | Role | Notes |
|---|---|---|---|
| `index(1).html` | `existing_ui_reference/index.html` | EWS Conversation AI page | Loads `style.css` and `script.js`; includes local demo `EWS_API_BASE_URL`, `EWS_LOCAL_DEMO_TOKEN`, `EWS_STT_ONLY_MODE` |
| `script(3).js` | `existing_ui_reference/script.js` | `ChatbotApp` controller | Bearer-auth API calls, chat/sessions, table renderer, modal, microphone multipart STT |
| `style(3).css` | `existing_ui_reference/style.css` | Current visual design | User-selected CSS must not be redesigned |

The reference assets are **unaltered byte-for-byte** except for packaged filenames that match the HTML `<link>`/`<script>` references. These are integration fixtures, **not a claim of secure production assets**. Retain the original copies outside the new backend project if desired.

## 3. Observed endpoints and exact client-side assumptions
| Route | Method | Observed request | Fields that the current script reads |
|---|---|---|---|
| `/health` | GET | No auth header added | JSON `{ "status": "healthy" }` or `{ "status": "ok" }` |
| `/ews-chatbot/chat` | POST | JSON `{ "message": string, "session_id": string/null, "user_id": string }` with Bearer | `session_id` or `sessionId`; `response` or `answer`/`message`/`content`; `results` or `data`; optional `sql_query` or `sqlQuery` |
| `/ews-chatbot/get_all_sessions` | GET | Bearer | Array or `{ "sessions": [...] }`; session `session_id`/`sessionId`/`id`, optional `title`, `first_message`, `updated_at`/`created_at`, `user_id` |
| `/ews-chatbot/load_session/{session_id}` | GET | Bearer, URI-encoded ID | Array or `{ "messages": [...] }`/`{ "history": [...] }`; each message reads `role`/`sender`, `content`/`message`/`text`, optional `results`/`data`, `sql_query`/`sqlQuery`, `timestamp`/`created_at` |
| `/api/v1/speech/transcriptions` | POST | Bearer + multipart `FormData`: `audio` Blob and `locale: "en-IN"`; `X-Request-ID` header | JSON `transcript` field, trimmed and appended to composer; **optional feature** |

The existing script does **not** call `/ews-chatbot/delete_session/{id}`; that route may be implemented as a backend capability for compatibility without adding a new button. It does **not** currently use the new internal `/api/v1/chat` JSON contract.

The current JS expects synchronous JSON; the backend must not require SSE, streamed tokens or WebSocket events. Optional nonbreaking upgrades need an explicit UI-owner change request.

## 4. Sample synthetic compatibility messages (not production data)
Chat request as sent by existing UI:
```json
{"message":"Show fictional account count by region","session_id":null,"user_id":"user1"}
```
Chat success response accepted by existing UI:
```json
{"session_id":"synthetic-s1","response":"Here are the authorized results for the reporting period.","results":[{"region":"Demo North","account_count":12},{"region":"Demo South","account_count":8}]}
```
Session list:
```json
{"sessions":[{"session_id":"synthetic-s1","title":"Account count by region","updated_at":"2026-10-16T00:00:00Z","user_id":"user1"}]}
```
Session detail:
```json
{"messages":[{"role":"user","content":"Show fictional account count by region"},{"role":"assistant","content":"Here are the authorized results.","results":[{"region":"Demo North","account_count":12}]}]}
```
Optional STT result:
```json
{"transcript":"Show fictional account count by region"}
```

## 5. Adapter architecture and responsibilities
1. Backend retains rich internal, versioned Pydantic models (`Principal`, `QueryRequest`, `AnswerEnvelope`, `Session`, `QueryProof`, `ClarificationRequest`) for all query/security semantics.
2. Implement a thin EWS compatibility API adapter that **converts between** observed existing JS shapes and internal contracts. No business rules, SQL execution or auth decisions in adapter serialization code.
3. Keep `/api/v1` internal/public typed endpoints if necessary for future clients. These do not require rebuilding the existing UI.
4. Preserve the existing client field aliases where observed but emit one stable canonical legacy response shape. Avoid breaking the JS while maintaining JSON schema tests.
5. Normalize approved result scalars to browser-safe objects/strings (Decimal/currency, Oracle date/timestamp, null); keep row count/size limits and masking. `results` must be an array of row objects; table rendering uses `Object.keys(results[0])`.
6. For unsupported/clarification/stale/truncated outcomes, translate typed backend states to a safe `response` message the existing renderer can display. Do not fabricate results or silently expose unimplemented chart types.
7. Omit `sql_query` unless a separately authorized policy permits exposing the actual approved SQL to this principal. Never put credentials, bind values or restricted physical schema in error messages.
8. Health route must be intentionally scoped to non-sensitive readiness/liveness; no internal endpoints/DSNs or tracebacks.
9. Include request IDs and tracing at API boundary. The old script does not supply client idempotency ID for chat; protect duplicate submissions server-side where feasible, but do not pretend it supports a retry token until UI integration changes are approved.

## 6. Critical security observations and gates
**A. Identity and user selector.** The HTML contains a user selector with `user1`/`demo_user`; JS also sends `user_id` in chat payload and filters session listings in the browser. This is only a UI/testing feature. Server must derive the effective identity from a validated token/session, deny mismatches as appropriate, and prevent cross-principal session reads/writes/deletes. Browser-side filtering does not enforce permissions.

**B. Demo bearer token.** HTML sets `window.EWS_LOCAL_DEMO_TOKEN` to a placeholder string; JS has `tokensByUser` placeholders. Do not store any production bearer credentials in published HTML or JS. Corporate SSO/session integration may require a **minimal authorized JS change**; until then, production launch is blocked, not solved by backend blindly trusting the selector or shared token.

**C. Microphone and STT.** HTML sets `EWS_STT_ONLY_MODE = true`, which suppresses the *initial* session fetch in the constructor; it does **not** prove sessions have been disabled everywhere. Confirm this flag and feature behavior during later integration. The script records microphone audio with `MediaRecorder`, accepts format variants, enforces a client-side 20 MiB limit, sends multipart form with `audio`/`locale`, and expects `transcript`. Server must validate MIME, size, duration, locale, quotas, retention and approved transcription provider. Speech remains optional and must not block text chat.

**D. External CSS/icon CDNs.** HTML loads Bulma and Font Awesome from external CDNs. Internal deployment requires company approval or approved local asset hosting, compatible CSP and integrity policy. Do not introduce new network dependencies without approval.

**E. XSS/CSP/error handling.** The script escapes displayed text and table cell values through `escapeHtml` and uses `innerText` for SQL modal, but those details do not replace a full browser security review. Backend returns plain text and typed JSON, no arbitrary model HTML. Check all dynamic fields, errors, form submissions and auth token exposure before production.

**F. SQL display.** A visible 'View SQL' button is created if `sql_query` is provided. Decide with data governance whether this is permitted, and redact/omit otherwise; bind values are not sent for display.

## 7. Backend-only implementation now
Required now: FastAPI scaffold, auth abstractions, `/ews-chatbot` contract fixture/adapter design, Pydantic schemas, error envelopes, API tests, synthetic sessions, core NL2SQL modules according to documents 01–34, and security deny tests. Tests should run with a mock client against FastAPI without launching the real UI. **No React/TypeScript/Vite/eslint/frontend scaffold, no browser build, no CSS redesign.**

At later integration: verify asset locations, approved hosting, CORS, tokens/auth, demo selector policy, health/CSP/CDNs, optional STT, session lifecycle, typed results, any visibility of SQL, accessibility/responsive handling. Browser tests only then, with explicit signoff.

## 8. Minimum acceptance tests
- Authenticated chat with expected user, successful response and `results: [{...}]`.
- Browser `user_id` mismatch/forgery and cross-user session access denied.
- New chat (`session_id: null`) returns server-issued ID; list/load ownership enforced.
- `GET /health` status compatible and non-sensitive.
- Saved history displays `role`, `content`, `results` with optional SQL only if permitted.
- Optional speech multipart happy/error paths and server-side limits; disabled feature returns explicit stable error.
- Ambiguous, unsupported, empty, denied, delayed and error cases map to safe response text/status as appropriate.
- No frontend code generation or changes as a side effect of backend tasks.
- Source preservation audit: all original backend architecture requirements retained; V4.1 front-end build duties only moved to later integration or removed as obsolete.

## 9. Approval record
**Fixed by user:** This specific supplied UI is the exclusive UI; integration later, do not build UI now.
**Still requires approval:** Corporate identity mechanism, production token/CSP policy, UI asset hosting/CDNs, STT provider/data retention, SQL visibility, browser safety, deployment and Oracle access. V4.1 model/retrieval/semantic/SQL gates remain unchanged.

## 10. Precedence / Codex directive
Read [00](./00_MASTER_DOCUMENT_REGISTER_AND_PRECODING_CHECKLIST.md), [16](./16_API_AUTH_AND_ERROR_CONTRACTS.md), [17](./17_FRONTEND_UX_RESULT_TABLES_AND_ACCESSIBILITY.md), [25](./25_IMPLEMENTATION_ROADMAP_DEPENDENCIES_AND_GATES.md), [28](./28_REPOSITORY_STRUCTURE_AND_TECHNOLOGY_ADRS.md), [30](./30_CODING_STANDARDS_CODEX_AND_CI.md), and [34](./34_TRACEABILITY_DECISIONS_AND_FINAL_REVIEW.md). **If an older historical baseline suggests building a UI, it is superseded by this decision.** Do not change architecture unrelated to UI. Build backend/API only until the owner asks to integrate the preserved UI.
