# 08 — Secure Entity, Identifier and Filter-Value Resolution

> **V4.2 FINAL UI DECISION (supersedes earlier UI assumptions):** The user-supplied `index.html`, `script.js`, and `style.css` are the **only UI** for this product. The application deliverable is a backend + adapters + tests. **Do not build React, TypeScript, Vite, new screens, a replacement UI, or a frontend scaffold.** Integrate the existing UI only in a later authorized milestone, without changing its appearance unless the owner separately approves a security or compatibility fix. See [35 Existing UI Integration](./35_EXISTING_UI_INTEGRATION_CONTRACT.md). All non-UI V4.1 NL-to-SQL requirements remain in force.

**Status:** Draft for review; no implementation or company production validation performed.  
**Document owner:** Backend + security + domain owner  
**Gate:** P0  
**Baseline reference:** V4 research/blueprint supplied on 2026-10-15.  
**Data policy:** Fictional examples only; actual company schema and customer data stay in approved office systems.

> **Core distinction:** this document specifies future behavior. It does not claim that these modules, controls, model benchmarks, or Oracle permissions are already deployed.

## Design specification

## Why this module is different from schema RAG
Metadata retrieval finds *columns* like `customer_name` or `region`. Value resolution finds an **authorized value** for a user phrase like “Northwind Supplies,” which may be an exact organization name, legal alias, code or several different rows. Do not treat vectors over real entity records as an automatic requirement: this risks indexing sensitive data and revealing unauthorized names.

## Pipeline
1. Parse candidate value phrases and expected entity type from typed question intent, without accepting raw SQL fragments.
2. Determine an allowlisted lookup source, matchable attributes and data class from the catalog.
3. Filter candidate values with the authenticated user’s database-enforced scope (and approved app policy).
4. Run parameterized exact/canonical normalized lookup first (case/spacing/punctuation policy explicit).
5. Optionally run DBA-approved limited prefix/alias search. Do not use unrestricted full scans or fuzzy disclosure on sensitive identity fields.
6. Return stable opaque entity IDs and masked display labels where authorized.
7. If zero authorized matches, return `NOT_FOUND`; if multiple valid matches, return `AMBIGUOUS` and offer safe distinguishing attributes only.
8. Attach resolved IDs as bind parameters; do not paste values into SQL text or model prompts unnecessarily.

## API contracts
`resolve_value(principal, entity_type_id, phrase, context, catalog_version) -> ResolvedValue | Clarification | Rejection`. `ResolvedValue` has an opaque internal ID, allowed column ID, typed bind value, permitted display string, freshness/lookup version and provenance. The full value must not be logged.

## Security rules
This module cannot enumerate unauthorized identifiers. Do not use whether hidden values exist as a different error response. Protect lookups from frequency abuse and enumeration; cap candidates, rate limits, and elapsed time. Sensitive value caches are disabled by default; if approved, partition by authorization context, bind expiry and encryption requirements.

## Tests
Test exact match, normalized alias, multiple identical names, ambiguous legal names, no authorized match, restricted fields, injection strings in names, Unicode, trailing spaces, historical name mapping, reuse after permissions change and result truncation. Include a negative test that embeds a full customer list into vectors—this must be forbidden by default.



## V4.1 value lookups bound to governed view dimensions
The value resolver accepts only a certified `dimension_id` or business-entity key exposed by an approved view, plus authenticated scope. It must not execute unconstrained string search across arbitrary Oracle columns. Exact alias/ID match precedes fuzzy candidates; fuzzy candidates are permission-filtered and require disambiguation where collisions exist. Use bind variables and default-deny cardinality/limit constraints; no real names/identifiers are placed in the metadata embedding corpus. A resolved value token has principal, snapshot, scope and expiry binding; the compiler receives typed parameters, not SQL fragments.
Tests: similar customer names belonging to different scopes, aliases across time, attempts to search disallowed attributes, missing results, coercion tricks and stale resolution tokens. Track leakage separately from matching recall.

---

## Deliverables / artifacts to review

Value resolver protocol, lookup policies, parameter binding model, ambiguity UI contract, sensitive data threat tests

## Acceptance tests and exit criteria

No unauthorized enumeration; correct alias resolution; safe ambiguous/not-found response; bind-only execution

## Open decisions and evidence required

Which business identifiers are allowed for lookups? Which source views can expose aliases? Are approximate matches authorized?

## Related documents

[04](./04_SEMANTIC_CATALOG_AND_GOVERNANCE.md), [06](./06_RETRIEVAL_LEXICAL_VECTOR_AND_RANKING.md), [09](./09_ROUTING_CONFIDENCE_AND_EXECUTION_PATHS.md), [10](./10_QUERY_PLAN_DSL_AND_VALIDATION.md), [15](./15_ORACLE_ADAPTER_PREFLIGHT_AND_RESOURCES.md), [21](./21_SECURITY_PRIVACY_THREAT_MODEL.md)

---

## Concrete resolver policies and typed examples
```json
{
  "entity_type_id": "customer",
  "input_phrase": "Northwind Supplies",
  "matching_policy": "certified_name_alias_exact",
  "catalog_version": "demo-v1"
}
```
The authenticated principal is attached server-side. A successful match returns `entity_ref`, `field_id`, and a typed bind value; it must **not** return an arbitrary `WHERE` SQL fragment. A disambiguation response may list approved masked location or entity subtype *only if that information is permitted for the principal*.

### Resolver result variants
- `unique_match`: single authorized stable record, allowed bind value and source freshness.
- `ambiguous`: bounded list of safe distinguishing options; clarification token expires and is bound to session/principal/catalog.
- `not_found`: no authorized match; identical public phrasing for truly absent versus hidden unauthorized records when required by policy.
- `lookup_not_allowed`: entity class not searchable; generic deny.
- `source_outdated`: canonical alias lookup lacks required historical effective-date data; clarify/reject.

### Operational controls
Prohibit value enumeration with wildcard-only, empty, or too-short queries; cap prefix matches and distinguish public-safe aliases from PII (personal addresses, PAN, account numbers) under company policies. Cache only schema-level matching policies by default. Bind customer values as Oracle driver parameters, with sensitive bind logging switched off. Untrusted values may contain SQL-like punctuation without gaining SQL syntax power.

### Failure tests
`"Acme' OR 1=1 --"` must be treated as a value, not SQL. Unknown names never trigger arbitrary full customer-table scans. Duplicate normalized names must clarify rather than arbitrarily choose first. Identity renaming across historical periods must respect as-of lookup policy. Two users with different row grants must not receive the same restricted candidate list. All tests run on synthetic data in the portable environment.

---

## Internal architecture and deployment policy
The resolver should be a **separate interface** from the metadata retriever. Search handles schema terms; value resolution handles a certified query's filter values. These can be executed sequentially for simplicity: route question → identify expected filter field/entity → authorize lookup view → resolve candidate value. The resolver should accept only parameterized, DBA-approved lookup templates and should not let Gemma compose its matching SQL.

### User-facing ambiguity example
User enters “Show sales for Northwind.” Approved reference contains Northwind Supplies and Northwind Retail. If the current principal may view both, return two **authorized** masked choices. If only one is visible, present only that authorized option or follow the company's existence-disclosure rule. Don't list unauthorized values or imply their existence. When the user chooses, store the stable entity reference bound to the session clarification token, check ownership, expire after a policy-set interval, and rerun the query through the normal validation flow.

### Data quality and index choice
A customer alias can change over time. Store value lookup policy for as-of mapping if required. Start with primary code and normalized exact name in approved reference views, not embeddings of customer records. Fuzzy suggestions should be separately approved, measured for false positives and subject to stricter enumeration protection. An unknown identifier should not cause unbounded lookup or raw customer-table traversal.

### Release acceptance
Demonstrate identical authorized results under exact and alias spelling; no collision incorrectly selects first match; malicious quotes are bound; unauthorized principal cannot enumerate names; stale resolution is invalidated on permission/catalog change; database read volume stays inside the approved lookup budget. Capture metrics as counts/latencies without logging sensitive phrases.
