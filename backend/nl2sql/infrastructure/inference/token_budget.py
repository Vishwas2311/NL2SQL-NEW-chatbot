"""Count the complete chat body with the selected runtime's own tokenizer."""

import json
import time
from threading import Event
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from nl2sql.domain.models import Failure
from nl2sql.settings import Settings


class _Count(BaseModel):
    model_config = ConfigDict(extra="ignore")
    input_tokens: int = Field(strict=True, ge=0, le=1_048_576)


def fit_payload(
    payload: dict[str, object],
    settings: Settings,
    client: httpx.Client,
    headers: dict[str, str],
    deadline: float,
    cancelled: Event | None,
) -> int | None:
    """At most two counts: remove optional evidence once, never truncate required contracts."""
    endpoint = settings.model_token_count_endpoint
    if settings.model_mode == "configured_http" and settings.model_token_budget == "provider":
        return None  # Server enforces context/output limits; byte and deadline guards remain local.
    if endpoint is None:
        if settings.data_classification != "synthetic":
            raise Failure(
                "MODEL_TOKENIZER_REQUIRED",
                "Configure the approved runtime token counter.",
                "unavailable",
            )
        return None  # Synthetic contract tests do not qualify a model's context window.
    origin = urlparse(settings.model_endpoint or "")
    target = urlparse(endpoint)
    if (
        (target.scheme, target.netloc) != (origin.scheme, origin.netloc)
        or target.query
        or target.fragment
        or target.username
        or target.password
    ):
        raise Failure(
            "MODEL_TOKENIZER_CONFIGURATION",
            "Token counting requires the model origin.",
            "unavailable",
        )
    message_key = "input" if settings.model_api == "responses" else "messages"
    messages = TypeAdapter(list[dict[str, str]]).validate_python(payload[message_key])
    for attempt in range(2):
        count = _count(endpoint, payload, client, headers, deadline, cancelled)
        if (
            count + settings.model_max_tokens + settings.model_token_safety_margin
            <= settings.model_context_tokens
        ):
            return count
        if attempt == 0:
            try:
                user = TypeAdapter(dict[str, str]).validate_json(messages[1]["content"])
                metadata = TypeAdapter(dict[str, object]).validate_json(user["metadata"])
            except (ValueError, KeyError):
                break
            if not metadata.get("schema_records"):
                break
            metadata["schema_records"] = []
            metadata["truncated"] = True
            user["metadata"] = json.dumps(metadata, separators=(",", ":"), sort_keys=True)
            messages[1] = {"role": "user", "content": json.dumps(user)}
            payload[message_key] = messages
    raise Failure(
        "MODEL_CONTEXT_BUDGET", "Narrow the question to fit the model context window.", "invalid"
    )


def _count(
    endpoint: str,
    payload: dict[str, object],
    client: httpx.Client,
    headers: dict[str, str],
    deadline: float,
    cancelled: Event | None,
) -> int:
    remaining = deadline - time.time()
    if cancelled is not None and cancelled.is_set():
        raise Failure("MODEL_CANCELLED", "The inference request was cancelled.", "conflict")
    if remaining <= 0:
        raise Failure("MODEL_TIMEOUT", "The inference request timed out.", "timeout")
    try:
        with client.stream(
            "POST", endpoint, json=payload, headers=headers, timeout=remaining
        ) as response:
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_bytes():
                if cancelled is not None and cancelled.is_set():
                    raise Failure(
                        "MODEL_CANCELLED", "The inference request was cancelled.", "conflict"
                    )
                if time.time() >= deadline:
                    raise Failure("MODEL_TIMEOUT", "The inference request timed out.", "timeout")
                if len(body) + len(chunk) > 16_000:
                    raise Failure(
                        "MODEL_TOKENIZER_INVALID", "Invalid token count response.", "unavailable"
                    )
                body.extend(chunk)
        return _Count.model_validate_json(bytes(body)).input_tokens
    except httpx.TimeoutException as error:
        raise Failure("MODEL_TIMEOUT", "The inference request timed out.", "timeout") from error
    except httpx.HTTPError as error:
        raise Failure(
            "MODEL_TOKENIZER_UNAVAILABLE", "Runtime token counting is unavailable.", "unavailable"
        ) from error
    except ValidationError as error:
        raise Failure(
            "MODEL_TOKENIZER_INVALID", "Invalid token count response.", "unavailable"
        ) from error
