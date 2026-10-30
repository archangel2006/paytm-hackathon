"""
Phone number helpers – normalise and mask.

Pure functions, no side effects, no imports from server or agent internals.
"""

from __future__ import annotations

import re


_DIGITS_ONLY = re.compile(r"\D")


def normalize(raw: str) -> str:
    """Normalise any Indian phone input to E.164 ``+91XXXXXXXXXX``.

    Accepted formats:
    - ``98765 43210``
    - ``+91 98765-43210``
    - ``919876543210``
    - ``09876543210``

    Raises ``ValueError`` for garbage input.
    """
    digits = _DIGITS_ONLY.sub("", raw)

    # Strip leading country code
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]

    if len(digits) != 10 or not digits.isdigit():
        raise ValueError(f"Cannot normalise phone number: {raw!r}")

    return f"+91{digits}"


def mask(e164: str) -> str:
    """Mask an E.164 number for safe logging: ``+91 98xxx xx210``."""
    if not e164.startswith("+91") or len(e164) != 13:
        return "***masked***"
    d = e164[3:]  # 10 digits
    return f"+91 {d[0:2]}xxx xx{d[7:]}"
