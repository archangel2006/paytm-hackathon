"""
agent/core/templates.py — Fixed message templates.

Template IDs MUST match what Person 1 submits to WhatsApp Business.
Each template has:
  - text: used when the 24-hour conversation window is open (free-form)
  - template_name: the WhatsApp-approved template name
  - template_params: ordered list of param names for the approved body

The channel layer (Person 1's router.py) decides between free text and template.
The agent never checks the 24-hour window itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from agent.domain.enums import Language


@dataclass
class Template:
    template_id: str
    language: Language
    text_fn: Callable[..., str]       # produces free-form text from kwargs
    template_name: str
    template_param_keys: list[str]    # ordered keys whose values become template_params


# ── Hindi / Hinglish intro ────────────────────────────────────
def _intro_hi(owner_name: str, **_: object) -> str:
    return (
        f"नमस्ते {owner_name} जी! आपकी दुकान के लिए Paytm Soundbox उपयोगी हो सकता है। "
        "क्या मैं आपको जानकारी भेजूं?"
    )


def _intro_en(owner_name: str, **_: object) -> str:
    return (
        f"Hello {owner_name}! A Paytm Soundbox could help your shop confirm payments instantly. "
        "Shall I share the details?"
    )


# ── Document request ──────────────────────────────────────────
def _doc_request(owner_name: str, **_: object) -> str:
    return (
        f"Hi {owner_name}, please send a clear photo of your PAN card and an address proof "
        "to continue with your Paytm onboarding."
    )


# ── Document re-request ───────────────────────────────────────
def _doc_rerequest(owner_name: str, doc_type: str = "document", **_: object) -> str:
    doc_label = "PAN card" if "pan" in doc_type.lower() else doc_type.replace("_", " ").title()
    return (
        f"Hi {owner_name}, the photo of your {doc_label} was not clear. "
        "Could you please send it again? Make sure the image is sharp and fully visible."
    )


# ── Visit confirmation ────────────────────────────────────────
def _visit_confirm(owner_name: str, date: str, time: str, fse_name: str, **_: object) -> str:
    return (
        f"Hi {owner_name}, our executive {fse_name} will visit your shop on {date} at {time}. "
        "They will install your Paytm Soundbox. Please keep the required documents handy."
    )


# ── Activation nudge ──────────────────────────────────────────
def _activation_nudge(owner_name: str, nudge_number: int = 1, **_: object) -> str:
    if nudge_number == 1:
        return (
            f"Hi {owner_name}! Your Paytm Soundbox is all set. "
            "Ask your next customer to scan the QR code — that's your first payment! 🎉"
        )
    return (
        f"Hi {owner_name}, just checking in — your Soundbox is ready but we haven't seen "
        "your first payment yet. Ask a customer to scan the QR to get started. "
        "Let me know if you need any help!"
    )


# ── Follow-up / re-engagement ─────────────────────────────────
def _followup(owner_name: str, **_: object) -> str:
    return (
        f"Hi {owner_name}, just checking in about your Paytm Soundbox. "
        "Reply here whenever you are ready — happy to help!"
    )


# ── Holding replies (escalation / discount) ───────────────────
def _holding_discount(owner_name: str, **_: object) -> str:
    return (
        f"Hi {owner_name}, I've noted your request and forwarded it to our team. "
        "They will get back to you soon. Thank you for your patience!"
    )


def _holding_escalation(owner_name: str, fse_name: str = "our executive", **_: object) -> str:
    return (
        f"Hi {owner_name}, I understand. {fse_name} will call you within 2 hours. "
        "You won't need to repeat anything — I've already shared your details with them."
    )


# ── Settlement explanation (template-filled from tool output) ─
def _settlement_ok(
    owner_name: str,
    amount: str = "",
    expected_date: str = "",
    **_: object,
) -> str:
    return (
        f"Hi {owner_name}, your settlement of ₹{amount} is on its way "
        f"and will be credited by {expected_date}. "
        "Settlements happen within 1 working day. Let me know if you have any questions!"
    )


def _settlement_delayed(
    owner_name: str,
    amount: str = "",
    expected_date: str = "",
    delay_reason: str = "a processing delay",
    **_: object,
) -> str:
    return (
        f"Hi {owner_name}, your settlement of ₹{amount} has been delayed due to {delay_reason}. "
        f"It should be credited by {expected_date}. "
        "I'll keep an eye on it — please reach out if it doesn't arrive by then."
    )


# ─────────────────────────────────────────────────────────────
# Public registry
# ─────────────────────────────────────────────────────────────

TEMPLATES: dict[str, Template] = {
    "saathi_intro_hi": Template(
        template_id="saathi_intro_hi",
        language=Language.HINDI,
        text_fn=_intro_hi,
        template_name="saathi_intro_hi",
        template_param_keys=["owner_name"],
    ),
    "saathi_intro_en": Template(
        template_id="saathi_intro_en",
        language=Language.ENGLISH,
        text_fn=_intro_en,
        template_name="saathi_intro_en",
        template_param_keys=["owner_name"],
    ),
    "saathi_doc_request": Template(
        template_id="saathi_doc_request",
        language=Language.ENGLISH,
        text_fn=_doc_request,
        template_name="saathi_doc_request",
        template_param_keys=["owner_name"],
    ),
    "saathi_doc_rerequest": Template(
        template_id="saathi_doc_rerequest",
        language=Language.ENGLISH,
        text_fn=_doc_rerequest,
        template_name="saathi_doc_rerequest",
        template_param_keys=["owner_name", "doc_type"],
    ),
    "saathi_visit_confirm": Template(
        template_id="saathi_visit_confirm",
        language=Language.ENGLISH,
        text_fn=_visit_confirm,
        template_name="saathi_visit_confirm",
        template_param_keys=["owner_name", "date", "time", "fse_name"],
    ),
    "saathi_activation_nudge": Template(
        template_id="saathi_activation_nudge",
        language=Language.ENGLISH,
        text_fn=_activation_nudge,
        template_name="saathi_activation_nudge",
        template_param_keys=["owner_name"],
    ),
    "saathi_followup": Template(
        template_id="saathi_followup",
        language=Language.ENGLISH,
        text_fn=_followup,
        template_name="saathi_followup",
        template_param_keys=["owner_name"],
    ),
    "saathi_holding_discount": Template(
        template_id="saathi_holding_discount",
        language=Language.ENGLISH,
        text_fn=_holding_discount,
        template_name="saathi_holding_discount",
        template_param_keys=["owner_name"],
    ),
    "saathi_holding_escalation": Template(
        template_id="saathi_holding_escalation",
        language=Language.ENGLISH,
        text_fn=_holding_escalation,
        template_name="saathi_holding_escalation",
        template_param_keys=["owner_name"],
    ),
    "saathi_settlement_ok": Template(
        template_id="saathi_settlement_ok",
        language=Language.ENGLISH,
        text_fn=_settlement_ok,
        template_name="saathi_settlement_ok",
        template_param_keys=["owner_name", "amount", "expected_date"],
    ),
    "saathi_settlement_delayed": Template(
        template_id="saathi_settlement_delayed",
        language=Language.ENGLISH,
        text_fn=_settlement_delayed,
        template_name="saathi_settlement_delayed",
        template_param_keys=["owner_name", "amount", "expected_date", "delay_reason"],
    ),
}


def render(template_id: str, **kwargs: object) -> tuple[str, str, list[str]]:
    """
    Render a template.

    Returns:
        (text, template_name, template_params)
        - text: free-form string for open 24h window
        - template_name: WhatsApp template name
        - template_params: ordered list of string parameter values
    """
    tpl = TEMPLATES.get(template_id)
    if not tpl:
        raise KeyError(f"Unknown template: {template_id!r}")
    text = tpl.text_fn(**kwargs)
    params = [str(kwargs.get(k, "")) for k in tpl.template_param_keys]
    return text, tpl.template_name, params


def intro_template_id(language: str) -> str:
    """Return the correct intro template ID for the given language."""
    if language == Language.ENGLISH:
        return "saathi_intro_en"
    return "saathi_intro_hi"   # hindi and hinglish both use the Hindi template

