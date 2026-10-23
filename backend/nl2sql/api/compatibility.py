"""Legacy display fields are added only at the EWS transport boundary."""

from nl2sql.domain.models import Failure


def failure_status(error: Failure) -> int:
    """HTTP status mapping belongs to transport; domain failures carry application categories."""
    return {
        "invalid": 422,
        "unauthenticated": 401,
        "denied": 403,
        "not_found": 404,
        "conflict": 409,
        "too_large": 413,
        "busy": 429,
        "internal": 500,
        "not_implemented": 501,
        "unavailable": 503,
        "timeout": 504,
    }[error.kind]


def error_payload(path: str, code: str, message: str) -> dict[str, object]:
    """Keep typed errors intact while the existing JavaScript reads detail/message."""
    payload: dict[str, object] = {"error": {"code": code, "message": message}}
    if path.startswith("/ews-chatbot/") or path == "/api/v1/speech/transcriptions":
        payload.update({"detail": message, "message": message, "response": message, "results": []})
    return payload
