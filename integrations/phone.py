"""
Phone number helpers – normalise and mask.

Pure functions, no side effects, no imports from server or agent internals.
"""

from __future__ import annotations

import re


_DIGITS_ONLY = re.compile(r"\D")


def normalize(raw: str) -> str:
    """Normalise phone input to an E.164-style number.

    Accepted formats:
    - ``98765 43210``
    - ``+91 98765-43210``
    - ``919876543210``
    - ``09876543210``
    - international numbers such as ``+1 (555) 212-3891``

    Raises ``ValueError`` for garbage input.
    """
    has_explicit_country_code = raw.strip().startswith("+")
    digits = _DIGITS_ONLY.sub("", raw)

    # Strip leading country code
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]

    if len(digits) == 10 and digits.isdigit():
        return f"+91{digits}"

    if has_explicit_country_code and 8 <= len(digits) <= 15 and digits.isdigit():
        return f"+{digits}"

    if not digits.isdigit():
        raise ValueError(f"Cannot normalise phone number: {raw!r}")
    raise ValueError(f"Unsupported phone number length: {raw!r}")


def mask(e164: str) -> str:
    """Mask an E.164 number for safe logging: ``+91 98xxx xx210``."""
    if not e164.startswith("+") or not 8 <= len(e164[1:]) <= 15:
        return "***masked***"
    if not e164.startswith("+91") or len(e164) != 13:
        return f"+{e164[1:-4]}xxxx"
    d = e164[3:]  # 10 digits
    return f"+91 {d[0:2]}xxx xx{d[7:]}"
