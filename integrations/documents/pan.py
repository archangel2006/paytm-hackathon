"""
PAN card number extraction and name matching.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# PAN format: five capital letters, four digits, one capital letter
_PAN_PATTERN = re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]")

# Common OCR confusions at specific positions
_OCR_FIX_MAP = {
    "O": "0", "o": "0",
    "I": "1", "l": "1", "i": "1",
    "S": "5", "s": "5",
    "B": "8",
    "Z": "2",
    "G": "6",
}


def _fix_ocr_confusions(text: str) -> str:
    """Fix common OCR confusions in digit positions of potential PAN strings.

    PAN format: AAAAA9999A
    Positions 5-8 should be digits, so we fix letter→digit confusions there.
    """
    lines = text.upper().split()
    fixed_tokens: list[str] = []

    for token in lines:
        if len(token) == 10:
            chars = list(token)
            # Positions 5-8 (0-indexed) should be digits
            for i in range(5, 9):
                if chars[i] in _OCR_FIX_MAP:
                    chars[i] = _OCR_FIX_MAP[chars[i]]
            # Position 0-4 and 9 should be letters
            for i in [0, 1, 2, 3, 4, 9]:
                if chars[i] == "0":
                    chars[i] = "O"
                elif chars[i] == "1":
                    chars[i] = "I"
                elif chars[i] == "5":
                    chars[i] = "S"
            fixed_tokens.append("".join(chars))
        else:
            fixed_tokens.append(token)

    return " ".join(fixed_tokens)


def find_pan(ocr_text: str) -> str | None:
    """Extract a PAN number from OCR text, fixing common confusions first.

    Returns the PAN string or ``None``.
    """
    fixed = _fix_ocr_confusions(ocr_text)
    match = _PAN_PATTERN.search(fixed)
    if match:
        return match.group()

    # Also try the raw text in case fixing made it worse
    match = _PAN_PATTERN.search(ocr_text.upper())
    return match.group() if match else None


def validate_pan_format(pan: str) -> bool:
    """Return True if the PAN string matches the expected format."""
    return bool(_PAN_PATTERN.fullmatch(pan))


def match_name(ocr_text: str, owner_name: str) -> bool | None:
    """Compare OCR lines against the owner name using fuzzy matching.

    Returns:
    - ``True`` if a line matches with score >= 80
    - ``False`` if lines were found but none matched
    - ``None`` if no name-like lines could be read
    """
    try:
        from rapidfuzz import fuzz
    except ImportError:
        logger.warning("rapidfuzz not installed, skipping name match")
        return None

    lines = [line.strip() for line in ocr_text.split("\n") if line.strip()]
    if not lines:
        return None

    # Filter to lines that could be names (at least 3 chars, mostly letters)
    name_lines = [
        line for line in lines
        if len(line) >= 3 and sum(c.isalpha() or c.isspace() for c in line) > len(line) * 0.6
    ]

    if not name_lines:
        return None

    best_score = 0.0
    for line in name_lines:
        score = fuzz.token_sort_ratio(line.upper(), owner_name.upper())
        best_score = max(best_score, score)

    if best_score >= 80:
        return True
    return False
