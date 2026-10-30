"""
Configuration read from environment variables.
All secrets live in ``.env`` – never commit that file.
"""

from __future__ import annotations

import os
from pathlib import Path


def _load_local_env() -> None:
    """Load the integrations .env without overwriting explicit process values."""
    candidates = (
        Path(__file__).with_name(".env"),
        Path.cwd() / ".env",
    )
    for path in candidates:
        if not path.is_file():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = value
        break


_load_local_env()

# ── WhatsApp Cloud API ───────────────────────────────────────────────────────
WHATSAPP_TOKEN: str = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "saathi-verify-token")
WHATSAPP_APP_SECRET: str = os.getenv("WHATSAPP_APP_SECRET", "")
WHATSAPP_API_VERSION: str = os.getenv("WHATSAPP_API_VERSION", "v21.0")

# ── Document quality ────────────────────────────────────────────────────────
BLUR_THRESHOLD: float = float(os.getenv("BLUR_THRESHOLD", "100"))

# ── Uploads ──────────────────────────────────────────────────────────────────
UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "data/uploads")
MAX_UPLOAD_MB: float = float(os.getenv("MAX_UPLOAD_MB", "10"))

# ── Templates (names must match the Agent doc section 8 / 4.3) ──────────────
TEMPLATES: dict[str, str] = {
    "saathi_intro_hi": "hi",
    "saathi_intro_en": "en",
    "saathi_doc_request": "en",
    "saathi_doc_rerequest": "en",
    "saathi_visit_confirm": "en",
    "saathi_activation_nudge": "en",
    "saathi_followup": "en",
}

# ── Allowed MIME types ───────────────────────────────────────────────────────
ALLOWED_IMAGE_MIMES: set[str] = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_AUDIO_MIMES: set[str] = {"audio/ogg", "audio/mpeg", "audio/mp4"}
ALLOWED_MIMES: set[str] = ALLOWED_IMAGE_MIMES | ALLOWED_AUDIO_MIMES

# ── WhatsApp send ────────────────────────────────────────────────────────────
SEND_TIMEOUT_SECONDS: int = int(os.getenv("SEND_TIMEOUT_SECONDS", "8"))
SEND_MAX_RETRIES: int = int(os.getenv("SEND_MAX_RETRIES", "3"))

# ── 24-hour window (seconds) ────────────────────────────────────────────────
WINDOW_SECONDS: int = 24 * 60 * 60
