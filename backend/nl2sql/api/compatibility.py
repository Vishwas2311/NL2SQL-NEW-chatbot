"""Legacy display fields are added only at the EWS transport boundary."""


def error_payload(path: str, code: str, message: str) -> dict[str, object]:
    """Keep typed errors intact while the existing JavaScript reads detail/message."""
    payload: dict[str, object] = {"error": {"code": code, "message": message}}
    if path.startswith("/ews-chatbot/") or path == "/api/v1/speech/transcriptions":
        payload.update({"detail": message, "message": message, "response": message, "results": []})
    return payload
