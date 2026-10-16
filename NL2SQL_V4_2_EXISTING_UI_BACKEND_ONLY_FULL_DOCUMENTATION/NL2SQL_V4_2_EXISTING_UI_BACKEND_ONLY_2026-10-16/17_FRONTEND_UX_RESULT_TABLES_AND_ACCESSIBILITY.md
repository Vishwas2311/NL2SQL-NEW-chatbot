# 17 — Existing EWS UI Capability, Later Integration and Accessibility Acceptance

**Status:** UI technology selected by user; integration, security approval and deployment not performed.  
**Owner:** Backend/API team + existing UI owner + security.  
**Gate:** P0 compatibility contract; integration later.

> **V4.2 scope:** The user-provided `index.html`, `script.js` and `style.css` are the **sole UI**. Do not rebuild or replace them. This document records present capabilities, deferred UX wishes and backend obligations. [35](./35_EXISTING_UI_INTEGRATION_CONTRACT.md) is the precise observed wire contract.

## Verified existing implementation (from uploaded files)
- Vanilla HTML, CSS, and JavaScript (`ChatbotApp`); **not** React/TypeScript/Vite. Third-party presentation dependencies currently loaded from Bulma and Font Awesome CDNs.
- Session sidebar, New Chat, session listing and loading; active session tag; chat composer and message rendering.
- Send via `POST /ews-chatbot/chat`; sessions via `GET /ews-chatbot/get_all_sessions` and `GET /ews-chatbot/load_session/{id}`; health `GET /health`.
- Table rendering from `results` array of row objects, and optional `sql_query` display/copy modal.
- Optional browser microphone recording uploads multipart audio to `POST /api/v1/speech/transcriptions`; it does not perform speech recognition locally.
- The current HTML sets `EWS_STT_ONLY_MODE = true` (initial session load suppressed); examine this configuration during authorized integration rather than assuming session UX is fully enabled.
- The current JS has a user selector and browser-side local bearer demo token configuration. **These are not a production auth design**; backend verifies principal and enforces session ownership independently.

## Product decision and work split
**Now:** build backend, typed internal contracts, mandatory EWS compatibility adapter contracts/mocks, synthetic tests, and safe result schemas. Do **not** build new UI pages or frontend project scaffolds.

**Later, after approval:** load the exact supplied assets in a secure internal host, configure approved authentication and CSP/CDN policy, perform real browser-to-backend contract tests and make only explicitly approved minimal compatibility/security patches. Preserve visual design, selectors and user behavior unless requested.

## Contract-preserving results
The existing renderer reads `data.response|answer|message|content`, `data.session_id|sessionId`, `data.results|data` and optional `data.sql_query|sqlQuery`; saved messages use `role|sender`, `content|message|text`, timestamps and optional rows/SQL. The backend compatibility mapper must provide these **in addition to**, not instead of, richer typed internal `AnswerEnvelope` metadata. Do not leak hidden physical schema or unauthorized SQL; if SQL viewing is disallowed, omit `sql_query`.

## Existing UI limitations and postponed enhancements (not implementation instructions)
The supplied files do **not** currently show a complete chart system, result pagination, delete-session button, streaming, advanced clarification controls, full enterprise authentication flow, rich provenance panel or approved export UI. Retain corresponding backend policies and typed fields where previously planned; adapt into safe text/table responses at first integration. These are future product changes requiring separate UI-owner approval, not instructions to build a new frontend.

## Security, compatibility and acceptance criteria
- Browser-supplied `user_id` and `userSelect` never authorize data; derive identity solely from verified credentials and tenant entitlements. Return 401/403 for mismatch rather than switching effective user.
- Browser literals `EWS_LOCAL_DEMO_TOKEN` or `tokensByUser` must not contain reusable production secrets; migration to approved auth requires a separate owner-approved patch.
- Test chat, sessions, health, optional STT multipart boundary/size, safe result rows, optional SQL visibility, error states and input escaping. Browser smoke tests are **integration-phase only**.
- Verify CDN resources, offline availability, CORS, CSP, XSS, CSRF (as applicable), accessibility, keyboard behavior, responsive layout and role-specific data before deployment.
- Preserve backward-compatible synchronous JSON endpoint behavior; do not require WebSockets/SSE/new UI framework in the backend.

## Preserved design intentions
Previously documented user journeys—clarification, charts, cancellation, pagination, feedback, export, accessibility and advanced results—remain feature candidates or backend requirements **where applicable**; they are **not** mandatory new UI implementation in this phase. See 02, 16, 19 and 35 for user-facing contract decisions.

---

## Historical V4 Baseline Requirements (reference only; superseded where V4.1 refines them)

> **Historical UI exclusion:** Any older requirement below to create a React/TypeScript/Vite frontend, new browser pages, screens, or UI build/test pipeline is superseded by the user decision. These are historical notes, **not implementation tasks**. Preserve existing capabilities for later integration via document 35.

> This is preserved from the earlier planning draft for comparison. The current V4.1 design section, companion docs 30–34, the approved ADR register, and subsequent validated contracts take precedence on changes explicitly addressed in the V4.1 refinement. Historical descriptions of optional vector providers, open SQL fallback, and late Oracle tests are **not** new mandatory decisions.


The following material records relevant requirements from the previously agreed V4 blueprint. The sections above are the detailed module design and take precedence where they add stricter controls. Original V4 is a **proposed architecture**, not independently verified production source.

# 15. Chatbot Frontend

This is a historical UX wishlist only; the supplied existing UI is the sole frontend. No new UI build is authorized.

## 15.1 Recommended stack

**Superseded: new React UI is out of scope. Use supplied vanilla HTML/CSS/JS UI.**

Historical rationale for a replaced choice; do not implement this stack.

The required EWS compatibility adapter preserves the uploaded UI contract; implement integration later.

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
