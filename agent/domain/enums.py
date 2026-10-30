"""
Enums for the Paytm Saathi agent.

These are the single source of truth for all enum values used across the system.
Server and frontend store/show them as plain strings. Never rename a value.
Tell the group before adding one.
"""
from enum import Enum


class LifecycleState(str, Enum):
    """Merchant lifecycle states."""
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


class ActionType(str, Enum):
    """Actions the agent planner can choose from."""
    SEND_INTRO = "SEND_INTRO"
    ANSWER_QUERY = "ANSWER_QUERY"
    REQUEST_DOCS = "REQUEST_DOCS"
    REREQUEST_DOC = "REREQUEST_DOC"
    SCHEDULE_VISIT = "SCHEDULE_VISIT"
    SEND_ACTIVATION_NUDGE = "SEND_ACTIVATION_NUDGE"
    EXPLAIN_SETTLEMENT = "EXPLAIN_SETTLEMENT"
    WAIT = "WAIT"
    ESCALATE = "ESCALATE"
    CLOSE_LEAD = "CLOSE_LEAD"
    OFFER_DISCOUNT = "OFFER_DISCOUNT"


class AutonomyLevel(str, Enum):
    """How autonomously the agent executes an action."""
    L1 = "L1"  # Suggest only; a person acts
    L2 = "L2"  # Draft and act after human approval
    L3 = "L3"  # Act alone within the rules


class ActionStatus(str, Enum):
    """Status of an agent action."""
    PROPOSED = "proposed"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    EXECUTED = "executed"
    REJECTED = "rejected"
    OVERRIDDEN = "overridden"
    BLOCKED = "blocked"
    FAILED = "failed"


class Intent(str, Enum):
    """Classified intent from merchant message."""
    GREETING = "greeting"
    INTEREST = "interest"
    ASK_FEES = "ask_fees"
    ASK_DOCUMENTS = "ask_documents"
    SEND_DOCUMENT = "send_document"
    AGREE_VISIT = "agree_visit"
    SETTLEMENT_QUERY = "settlement_query"
    DEVICE_ISSUE = "device_issue"
    COMPLAINT = "complaint"
    ASK_DISCOUNT = "ask_discount"
    ASK_HUMAN = "ask_human"
    OPT_OUT = "opt_out"
    NOT_INTERESTED = "not_interested"
    OTHER = "other"


class Language(str, Enum):
    """Language of the merchant."""
    HINDI = "hindi"
    HINGLISH = "hinglish"
    ENGLISH = "english"


class Channel(str, Enum):
    """Communication channel."""
    WHATSAPP = "whatsapp"
    SIMULATOR = "simulator"


class DocType(str, Enum):
    """Document type for KYC."""
    PAN = "pan"
    ADDRESS_PROOF = "address_proof"


class DocQuality(str, Enum):
    """Quality assessment of a document image."""
    OK = "ok"
    BLURRY = "blurry"
    UNREADABLE = "unreadable"


class HandoffTarget(str, Enum):
    """Who receives the handoff."""
    FSE = "fse"
    SUPPORT = "support"

