"""
WhatsApp Cloud API client.

Credentials are read from the process environment through integrations.settings.
"""

from __future__ import annotations

import logging
import time

import httpx

from agent.ports import SendResult
from integrations import settings
from integrations.errors import is_retryable_status, map_wa_error

logger = logging.getLogger(__name__)
_BASE_URL = "https://graph.facebook.com"


def _url() -> str:
    return f"{_BASE_URL}/{settings.WHATSAPP_API_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer " + settings.WHATSAPP_TOKEN,
        "Content-Type": "application/json",
    }


def send_text(to: str, body: str) -> SendResult:
    if not settings.WHATSAPP_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        return SendResult(ok=False, error_code="NOT_CONFIGURED")
    return _send_with_retry({
        "messaging_product": "whatsapp",
        "to": to.lstrip("+"),
        "type": "text",
        "text": {"body": body},
    })


def send_template(to: str, template_name: str, language_code: str, params: list[str]) -> SendResult:
    if not settings.WHATSAPP_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        return SendResult(ok=False, error_code="NOT_CONFIGURED")
    components = []
    if params:
        components.append({
            "type": "body",
            "parameters": [{"type": "text", "text": value} for value in params],
        })
    return _send_with_retry({
        "messaging_product": "whatsapp",
        "to": to.lstrip("+"),
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
            "components": components,
        },
    })


def _send_with_retry(payload: dict) -> SendResult:
    last_error = ""
    for attempt in range(1, settings.SEND_MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=settings.SEND_TIMEOUT_SECONDS) as client:
                response = client.post(_url(), json=payload, headers=_headers())
            if 200 <= response.status_code < 300:
                data = response.json()
                messages = data.get("messages", [])
                return SendResult(
                    ok=True,
                    provider_message_id=messages[0].get("id") if messages else None,
                )
            try:
                error = response.json().get("error", {})
            except ValueError:
                error = {}
            if not is_retryable_status(response.status_code):
                return SendResult(
                    ok=False,
                    error_code=map_wa_error(error.get("code")),
                    error_detail=error.get("message", response.text[:200]),
                )
            last_error = f"HTTP {response.status_code}"
        except (httpx.TimeoutException, httpx.ConnectError, OSError) as exc:
            last_error = str(exc)
        if attempt < settings.SEND_MAX_RETRIES:
            time.sleep(2 ** (attempt - 1))
    return SendResult(ok=False, error_code="SEND_FAILED", error_detail=last_error)
