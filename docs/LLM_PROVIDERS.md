# Configurable planning providers

Implementation scope: local/OpenAI-compatible and Azure HTTP planning through Chat
Completions or Responses. Provider selection must be independent of Oracle/SQLite,
Redis, graph/vector storage and embedding selection. No provider SDK or model download
is required. A saved MiniLM directory is an encoder, not a planning model server.

The new `configured_http` mode retains host allowlists, TLS, bounded requests/replies,
deadlines, strict typed decisions and independent authorization/SQL validation. Restricted
metadata requires explicit endpoint authorization. Network policy selects private-address
endpoints or explicitly approved HTTPS, rather than inferring approval from a vendor name.
Legacy disabled/scripted/private_http/hosted_http behavior stays compatible.

Acceptance: exercise both wire protocols, Azure API-key and bearer authentication,
versioned endpoints, deployment/response identities, reasoning-compatible parameters,
JSON schema/object/text output, provider-enforced context limits or optional same-origin
runtime counting, denied egress/tools/truncation/invalid output and the complete pipeline.
All tests use synthetic data and local/fake endpoints. Live office providers and their
permissions, capacity and model accuracy require separate office qualification.

Provider budget mode sends an output cap and relies on the selected server's own context
limit. Local context bytes, deadline and response bytes remain bounded; it does not claim
exact pre-generation input counting. Runtime budget mode preserves the optional complete
payload counter with output/safety reserve. Never invent a token-count URL for a provider.

Protocol references:

- https://learn.microsoft.com/en-us/rest/api/microsoft-foundry/azureopenai/chat
- https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/responses
- https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/reasoning
- https://docs.ollama.com/api/openai-compatibility
- https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/structured-outputs

## Select a provider

Edit the private office environment file, outside Git. These are planning-model settings;
the MiniLM path and `NL2SQL_EMBEDDING_*` settings stay separate. Use the full operation URL,
not just the resource root. Selecting a vendor/model name does not start a model server.

| Setting | Local compatible server | Azure Chat Completions | Azure Responses |
|---|---|---|---|
| `NL2SQL_MODEL_MODE` | `configured_http` | `configured_http` | `configured_http` |
| `NL2SQL_MODEL_API` | `chat_completions` | `chat_completions` | `responses` |
| `NL2SQL_MODEL_ENDPOINT` | `http://127.0.0.1:11434/v1/chat/completions` | `https://<resource>.openai.azure.com/openai/v1/chat/completions` | `https://<resource>.openai.azure.com/openai/v1/responses` |
| `NL2SQL_MODEL_NAME` | Exact installed model ID | Your deployment name | Your deployment name |
| `NL2SQL_APPROVED_MODEL_HOSTS` | `'["127.0.0.1"]'` | `'["<resource>.openai.azure.com"]'` | Same Azure hostname |
| `NL2SQL_MODEL_AUTH` | `none`, or your server's auth | `api_key`, or `bearer` for an issued Entra token | Same |
| `NL2SQL_MODEL_NETWORK` | `private` | `approved_https`, or `private` for working Private Link/DNS | Same |
| `NL2SQL_MODEL_TOKEN_BUDGET` | `provider` | `provider` | `provider` |
| `NL2SQL_MODEL_TOKEN_PARAMETER` | `max_tokens` | `max_completion_tokens` for reasoning models | Ignored; sends `max_output_tokens` |
| `NL2SQL_MODEL_TEMPERATURE` | `null` to omit; otherwise supported numeric value | `null` to omit unsupported temperature | Same |

Populate `NL2SQL_MODEL_KEY` privately when needed. The bearer option supplies a token;
automatic Entra token acquisition/refresh is not implemented. Modern Azure v1 usually
does not need an API version query. For a classic deployment URL, either include its
single `?api-version=...` query or set `NL2SQL_MODEL_API_VERSION`, never both. Arbitrary URL
query parameters, embedded credentials and redirects are rejected.

After actual endpoint approval for restricted metadata, set
`NL2SQL_MODEL_RESTRICTED_DATA_AUTHORIZED=true`. This records existing approval; it does not
create it. Public API-key endpoints are not automatically authorized merely because a key
works. Private mode requires private DNS addresses and verified TLS except loopback HTTP.
Approved HTTPS deliberately permits the selected allowlisted HTTPS endpoint without that
private-address assumption. No company endpoint is contacted by local test execution.

For deployment aliases, set `NL2SQL_MODEL_RESPONSE_IDS` to a JSON array of verified returned
model IDs, for example `'["<verified-model-version>"]'`. Without it, the returned ID must
match `NL2SQL_MODEL_NAME`. Wildcards and silent acceptance of any returned model are not used.

Set `NL2SQL_MODEL_REASONING_EFFORT` only if supported by that model. Choose its real context
window and a suitable `NL2SQL_MODEL_MAX_TOKENS` (including reasoning tokens where applicable),
within the configured context reserve. Incomplete/refused output is denied, never executed.
Increase a small output budget only after measuring that model; no setting guarantees that
an arbitrary model can produce a correct plan within the request deadline.

`NL2SQL_MODEL_OUTPUT_MODE=json_schema` uses a portable strict schema on the wire while full
Pydantic constraints are checked locally. For servers without structured output, explicitly
select `json_object` or `text_json`; both still undergo the same strict parser, grounding,
permission, compiler and independent SQL validation. The typed schema is included in context
for these modes. No raw SQL fallback or automatic mode downgrade is introduced.

Native Anthropic/Gemini/Ollama-specific request formats are not translated by these two
protocols. Use an approved compatible endpoint or a separately implemented registered adapter.

## Existing profiles and connection check

Updating/cloning the repository does not overwrite `.env`, `office.json`, `office.env`, model
files or existing data. The installer also preserves existing profiles. For an old profile,
explicitly set the new `configured_http` fields above in its selected private environment
file. This overrides old JSON defaults. Provider budget mode ignores any old count URL;
clear that field to avoid confusion. Legacy `private_http` still requires its existing
runtime counter; legacy `hosted_http` remains synthetic-only.

From the project root in PowerShell, use the generated private profile paths:

```powershell
.\.venv\Scripts\python.exe -m nl2sql check-model --settings "$env:LOCALAPPDATA\NL2SQL\office\office.json" --env-file "$env:LOCALAPPDATA\NL2SQL\office\office.env"
```

This is an explicit outbound model probe using synthetic content. It tests authentication,
selected wire protocol, returned identity and typed output, closes its client, and never
opens Oracle or executes a query. A passing probe is not business accuracy or load qualification.
Then use the normal `validate-config` and office installer/startup flow; signed metadata,
Oracle context/grants, identity and Redis requirements remain in force.

Safe diagnostics: `MODEL_AUTHENTICATION` means rejected credentials/access;
`MODEL_REQUEST_REJECTED` means check the operation URL, deployment, protocol or parameters;
`MODEL_IDENTITY` means verify the returned model ID; `MODEL_CONTEXT_BUDGET` means narrow the
context or correct the approved budget; `MODEL_INVALID_JSON` means no valid complete typed
decision was returned. Provider response bodies and keys are never printed in these messages.
