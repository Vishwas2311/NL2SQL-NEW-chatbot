"""HTTP protocol differences stay outside planning, permissions and SQL compilation."""

import json
import re
from typing import cast
from urllib.parse import parse_qsl, urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from nl2sql.domain.models import Failure
from nl2sql.infrastructure.http_policy import private_endpoint
from nl2sql.settings import Settings


def configured_endpoint(settings: Settings) -> None:
    """An allowlisted HTTPS provider is distinct from a private-address deployment."""
    if (
        settings.data_classification == "restricted"
        and not settings.model_restricted_data_authorized
    ):
        raise ValueError("Authorize the selected model endpoint for restricted metadata")
    endpoint = urlparse(settings.model_endpoint or "")
    parameters = parse_qsl(endpoint.query, keep_blank_values=True)
    if (
        endpoint.hostname not in settings.approved_model_hosts
        or any((endpoint.username, endpoint.password, endpoint.fragment))
        or endpoint.scheme not in {"http", "https"}
        or (endpoint.query and not parameters)
    ):
        raise ValueError("Configure an allowlisted model URL without credentials or URL overrides")
    if parameters and (
        len(parameters) != 1
        or parameters[0][0] != "api-version"
        or not re.fullmatch(r"[a-zA-Z0-9._-]{1,40}", parameters[0][1])
    ):
        raise ValueError("Only a single explicit API version is allowed in the model URL")
    if endpoint.port is not None and not 1 <= endpoint.port <= 65535:
        raise ValueError("Invalid model endpoint port")
    if parameters and settings.model_api_version:
        raise ValueError("Configure the API version once, in the URL or model_api_version")
    if settings.model_network == "private":
        private_endpoint(endpoint._replace(query="").geturl(), settings.approved_model_hosts)
    elif endpoint.scheme != "https":
        raise ValueError("Approved hosted inference requires verified HTTPS")


def authorize_context(context: str, settings: Settings) -> None:
    """A model setting never downgrades the assembled catalog's classification."""
    try:
        metadata = TypeAdapter(dict[str, object]).validate_json(context)
    except ValueError:
        metadata = {}
    classification = metadata.get("classification")
    if classification not in ("synthetic", "restricted") or (
        classification == "restricted"
        and (
            settings.data_classification != "restricted"
            or not settings.model_restricted_data_authorized
        )
    ):
        raise Failure(
            "EGRESS_DENIED", "The model endpoint is not authorized for this context.", "denied"
        )


def strict_schema(value: object) -> object:
    """Use the portable wire subset; full Pydantic constraints still validate returned plans."""
    if isinstance(value, list):
        return [strict_schema(item) for item in cast(list[object], value)]
    if not isinstance(value, dict):
        return value
    result = {
        key: strict_schema(item)
        for key, item in cast(dict[str, object], value).items()
        if key
        not in {
            "default",
            "const",
            "format",
            "pattern",
            "minLength",
            "maxLength",
            "minimum",
            "maximum",
            "exclusiveMinimum",
            "exclusiveMaximum",
            "multipleOf",
            "minItems",
            "maxItems",
            "uniqueItems",
            "contains",
            "minContains",
            "maxContains",
            "minProperties",
            "maxProperties",
            "patternProperties",
            "propertyNames",
            "unevaluatedProperties",
            "unevaluatedItems",
        }
    }
    if "const" in value:
        result["enum"] = [cast(dict[str, object], value)["const"]]
    properties = result.get("properties")
    if isinstance(properties, dict):
        result["required"] = list(cast(dict[str, object], properties))
        result["additionalProperties"] = False
    return result


def configure_payload(payload: dict[str, object], settings: Settings) -> dict[str, object]:
    """Select capabilities explicitly; never guess a provider from its hostname/model name."""
    if settings.model_temperature is None:
        payload.pop("temperature", None)
    else:
        payload["temperature"] = settings.model_temperature
    if settings.model_reasoning_effort is not None:
        payload["reasoning_effort"] = settings.model_reasoning_effort
    if settings.model_token_parameter != "max_tokens":
        payload[settings.model_token_parameter] = payload.pop("max_tokens")
    if settings.model_mode == "configured_http" and "response_format" in payload:
        payload["response_format"] = strict_schema(payload["response_format"])
    if settings.model_api == "responses":
        payload["input"] = payload.pop("messages")
        payload["max_output_tokens"] = payload.pop(settings.model_token_parameter)
        response_format = cast(dict[str, object], payload.pop("response_format", {}))
        if response_format:
            format_spec = response_format.get("json_schema", response_format)
            payload["text"] = {
                "format": {**cast(dict[str, object], format_spec), "type": response_format["type"]}
            }
        if "reasoning_effort" in payload:
            payload["reasoning"] = {"effort": payload.pop("reasoning_effort")}
        payload.update(store=False, truncation="disabled")
    return payload


class _Text(BaseModel):
    type: str
    text: str = ""


class _Item(BaseModel):
    type: str
    role: str | None = None
    status: str | None = None
    content: tuple[_Text, ...] = ()
    tool_calls: tuple[dict[str, object], ...] | None = None
    function_call: dict[str, object] | None = None


class _Usage(BaseModel):
    input_tokens: int = Field(strict=True, ge=0)
    output_tokens: int = Field(strict=True, ge=0)
    total_tokens: int = Field(strict=True, ge=0)


class _Response(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    object: str
    model: str
    status: str
    output: tuple[_Item, ...]
    usage: _Usage | None = None


def response_as_chat(data: bytes) -> bytes:
    """Normalize only a completed text message; tools/refusals/truncation never become plans."""
    reply = _Response.model_validate_json(data)
    messages = [item for item in reply.output if item.type == "message"]
    if (
        reply.object != "response"
        or reply.status != "completed"
        or len(messages) != 1
        or any(item.type not in {"message", "reasoning"} for item in reply.output)
    ):
        raise Failure(
            "MODEL_INVALID_JSON",
            "The model returned an incomplete or non-text plan.",
            "unavailable",
        )
    if (
        messages[0].role != "assistant"
        or messages[0].status not in {None, "completed"}
        or messages[0].tool_calls
        or messages[0].function_call
        or not messages[0].content
        or any(part.type != "output_text" for part in messages[0].content)
    ):
        raise Failure(
            "MODEL_INVALID_JSON",
            "The model returned an incomplete or non-text plan.",
            "unavailable",
        )
    usage = reply.usage
    return json.dumps(
        {
            "id": reply.id,
            "object": "chat.completion",
            "created": 0,
            "model": reply.model,
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": "".join(part.text for part in messages[0].content),
                    },
                }
            ],
            "usage": {
                "prompt_tokens": usage.input_tokens,
                "completion_tokens": usage.output_tokens,
                "total_tokens": usage.total_tokens,
            }
            if usage
            else None,
        }
    ).encode()


def provider_failure(
    error: httpx.HTTPStatusError, body: bytes, settings: Settings
) -> Failure | None:
    """Inspect bounded error codes only; provider messages can contain private prompts."""
    status = error.response.status_code
    if status == 400:
        try:
            detail = TypeAdapter(dict[str, dict[str, object]]).validate_json(body)
        except ValueError:
            detail = {}
        if detail.get("error", {}).get("code") in (
            "context_length_exceeded",
            "context_window_exceeded",
        ):
            return Failure(
                "MODEL_CONTEXT_BUDGET",
                "Narrow the question to fit the model context window.",
                "invalid",
            )
    if settings.model_mode == "configured_http":
        if status in {401, 403}:
            return Failure(
                "MODEL_AUTHENTICATION",
                "Model authentication or endpoint access was rejected.",
                "unavailable",
            )
        if status in {400, 404, 422}:
            return Failure(
                "MODEL_REQUEST_REJECTED",
                "Check the model URL, deployment, API and supported request parameters.",
                "unavailable",
            )
    return None
