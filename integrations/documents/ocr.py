"""
OCR using Tesseract via ``pytesseract``.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)


def extract_text(gray: np.ndarray) -> str:
    """Run Tesseract OCR on a grayscale image and return the raw text.

    Returns an empty string if Tesseract is not installed or fails.
    """
    try:
        import pytesseract

        text = pytesseract.image_to_string(
            gray,
            lang="eng",
            config="--psm 6",  # page segmentation mode 6: uniform block
        )
        return text.strip()
    except Exception:
        logger.exception("OCR failed")
        return ""
