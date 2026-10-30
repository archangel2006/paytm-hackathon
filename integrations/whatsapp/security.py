"""
HMAC-SHA256 signature verification for WhatsApp webhooks.
"""

from __future__ import annotations

import hashlib
import hmac

from integrations import settings


def verify_signature(body: bytes, header_value: str | None, app_secret: str | None = None) -> bool:
    """Verify the ``X-Hub-Signature-256`` header.

    Returns ``True`` only when the configured app secret validates the body.
    """
    secret = app_secret if app_secret is not None else settings.WHATSAPP_APP_SECRET
    if not secret:
        return True
    if not header_value:
        return False

    # Header format: "sha256=<hex>"
    if not header_value.startswith("sha256="):
        return False

    expected_sig = header_value[7:]
    computed = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed, expected_sig)
