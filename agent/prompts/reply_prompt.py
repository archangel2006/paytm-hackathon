"""
agent/prompts/reply_prompt.py — Reply generation prompt builder.

Used when the agent needs to write a free-form merchant-facing reply
grounded in retrieved policy passages.
"""
from __future__ import annotations


def build(
    merchant_name: str,
    language: str,
    question: str,
    passages: list[dict],
) -> str:
    passages_text = "\n\n".join(
        f"Source: {p['source']}\n{p['text']}" for p in passages
    ) if passages else "No relevant policy found."

    return f"""You are Saathi, a helpful Paytm assistant.
Write a SHORT reply to the merchant's question using ONLY the policy passages provided below.

Merchant name: {merchant_name}
Language to reply in: {language}
Merchant's question: {question}

Policy passages:
---
{passages_text}
---

Rules:
- Reply ONLY in {language}. If language is 'hindi', write in Hindi (Devanagari or Hinglish is fine).
- Use ONLY information from the policy passages — do NOT invent fees, dates, or amounts.
- Keep the reply under 100 words.
- Be friendly and professional.
- Do NOT offer discounts, loans, or make any commitments not in the policy.

Respond with ONLY the merchant-facing message text."""

