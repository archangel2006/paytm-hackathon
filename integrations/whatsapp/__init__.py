"""
WhatsApp sub-package.

Exposes a ``status()`` helper for the server's health endpoint.
"""

from __future__ import annotations

from integrations import settings


def status() -> str:
    """Return ``configured`` or ``not_configured`` for the health check."""
    if settings.WHATSAPP_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID:
        return "configured"
    return "not_configured"
