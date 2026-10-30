"""
Maps WhatsApp Cloud API error codes to ``SendResult`` error strings.
"""

from __future__ import annotations

# Known error codes from the WhatsApp Cloud API documentation.
_WA_ERROR_MAP: dict[int, str] = {
    190: "WHATSAPP_AUTH_EXPIRED",  # expired or invalid access token
    131047: "WINDOW_CLOSED",       # outside 24-hour window
    131030: "RECIPIENT_NOT_ALLOWED",  # not on the test allowed list
    132000: "TEMPLATE_PARAM_MISMATCH",
    131031: "ACCOUNT_NOT_VERIFIED",
    131051: "UNSUPPORTED_MESSAGE_TYPE",
    130429: "RATE_LIMIT_HIT",
    131026: "MESSAGE_NOT_SENT",
    131021: "RECIPIENT_NOT_WHATSAPP_USER",
    131009: "PARAM_VALUE_NOT_VALID",
    132001: "TEMPLATE_NOT_FOUND",
    132005: "TEMPLATE_HYDRATED_TEXT_TOO_LONG",
    132007: "TEMPLATE_FORMATTING_MISMATCH",
    132012: "TEMPLATE_PAUSED",
    132015: "TEMPLATE_REJECTED",
}


def map_wa_error(error_code: int | None) -> str:
    """Return a human-readable error string for a WhatsApp error code."""
    if error_code is None:
        return "UNKNOWN_ERROR"
    return _WA_ERROR_MAP.get(error_code, f"WA_ERROR_{error_code}")


def is_retryable_status(http_status: int) -> bool:
    """Return True if the HTTP status suggests a transient failure worth retrying."""
    return http_status >= 500 or http_status == 429
