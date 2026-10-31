"""
agent/prompts/nlu_prompt.py — NLU classification prompt builder.

Version: v1
"""
from __future__ import annotations

import json

_INTENTS = [
    "greeting", "interest", "ask_fees", "ask_documents", "send_document",
    "agree_visit", "settlement_query", "device_issue", "complaint",
    "ask_discount", "ask_human", "opt_out", "not_interested", "other",
]

_SCHEMA = {
    "intent": f"one of: {', '.join(_INTENTS)}",
    "language": "one of: hindi, hinglish, english",
    "sentiment": "float from -1.0 (very angry) to 1.0 (very happy)",
    "wants_human": "bool — true if the merchant explicitly wants to talk to a person",
    "mentions_money": "bool — true if fees, charges, or money are mentioned",
    "confidence": "float 0.0–1.0 representing classification confidence",
}


def build(text: str, context_summary: str = "") -> str:
    return f"""You are classifying a merchant message for the Paytm Saathi AI system.

Context: {context_summary or "No additional context."}

Merchant message:
\"\"\"{text}\"\"\"

Classify this message and respond with ONLY valid JSON matching this schema:
{json.dumps(_SCHEMA, indent=2)}

Rules:
- intent must be exactly one of the listed values
- language must be exactly one of: hindi, hinglish, english
- sentiment: -1.0 is very angry/abusive, 0.0 is neutral, 1.0 is very happy
- wants_human: true if merchant uses words like "manager", "human", "baat karao"
- mentions_money: true if merchant mentions fees, charges, payments, or amounts
- Consider every clause in compound or conversational messages. If any clause asks about
  fees, rentals, or charges, use ask_fees rather than classifying only the first clause.
- confidence: how confident you are in the intent (0.0–1.0)

Respond with ONLY the JSON object, no other text."""
