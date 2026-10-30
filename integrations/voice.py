"""
Voice note handling – STRETCH feature.

Only implement after everything else works.
Downloads audio, converts if needed, transcribes with speech-to-text,
and sends an ``IncomingEvent(kind="voice", text=<transcript>)``.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def transcribe_audio(file_path: str) -> str | None:
    """Transcribe an audio file to text.

    Returns the transcript or ``None`` if transcription fails.
    This is a stub – implement with Whisper or a speech-to-text API
    when the stretch goal is reached.
    """
    logger.info("Voice transcription requested for %s (stub – not implemented)", file_path)
    return None
