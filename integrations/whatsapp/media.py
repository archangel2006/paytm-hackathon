from __future__ import annotations

import logging
import os

import httpx

from integrations import settings

logger = logging.getLogger(__name__)


async def download_media(
    media_id: str,
    mime_type: str,
    merchant_phone: str,
    event_id: str,
) -> tuple[str | None, str | None]:
    if mime_type not in settings.ALLOWED_MIMES:
        logger.warning("Rejected media with unsupported MIME type")
        return None, None
    headers = {"Authorization": "Bearer " + settings.WHATSAPP_TOKEN}
    base_url = f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}"
    try:
        async with httpx.AsyncClient(timeout=settings.SEND_TIMEOUT_SECONDS) as client:
            metadata = await client.get(f"{base_url}/{media_id}", headers=headers)
            metadata.raise_for_status()
            download_url = metadata.json().get("url")
            if not download_url:
                return None, None
            response = await client.get(download_url, headers=headers)
            response.raise_for_status()
            content = response.content
        if len(content) > int(settings.MAX_UPLOAD_MB * 1024 * 1024):
            return None, None
        safe_phone = merchant_phone.replace("+", "").replace(" ", "")
        directory = os.path.join(settings.UPLOAD_DIR, safe_phone)
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, f"{event_id}.{_mime_to_ext(mime_type)}")
        with open(path, "wb") as file:
            file.write(content)
        return path, mime_type
    except (httpx.HTTPError, OSError, ValueError):
        logger.exception("WhatsApp media download failed")
        return None, None


def _mime_to_ext(mime: str) -> str:
    return {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "audio/ogg": "ogg",
        "audio/mpeg": "mp3",
        "audio/mp4": "m4a",
    }.get(mime, "bin")
