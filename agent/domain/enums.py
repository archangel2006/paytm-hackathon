"""
Canonical enums shared across the project.
Owned by Person 2 (agent). Other areas import from here.
"""

from enum import Enum


class Language(str, Enum):
    HINDI = "hindi"
    HINGLISH = "hinglish"
    ENGLISH = "english"


class Channel(str, Enum):
    WHATSAPP = "whatsapp"
    SIMULATOR = "simulator"


class DocType(str, Enum):
    PAN = "pan"
    AADHAAR = "aadhaar"
    ADDRESS_PROOF = "address_proof"


class DocQuality(str, Enum):
    OK = "ok"
    BLURRY = "blurry"
    UNREADABLE = "unreadable"


class LifecycleState(str, Enum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    ENGAGED = "ENGAGED"
    DOCS_PENDING = "DOCS_PENDING"
    DOCS_VERIFIED = "DOCS_VERIFIED"
    VISIT_SCHEDULED = "VISIT_SCHEDULED"
    INSTALLED = "INSTALLED"
    ACTIVATING = "ACTIVATING"
    ACTIVATED = "ACTIVATED"
    AT_RISK = "AT_RISK"
    DORMANT = "DORMANT"
    LOST = "LOST"
