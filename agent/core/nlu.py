"""
agent/core/nlu.py — Natural Language Understanding.

classify(text, context) -> NluResult

Strategy:
1. Try keyword-based classification first (always fast, zero cost, no network)
2. If keyword confidence is low (ambiguous text), call the LLM
3. If LLM fails or times out, fall back to keyword result
"""
from __future__ import annotations

import logging
import re
from typing import Literal

from pydantic import BaseModel

from agent.domain.enums import Intent, Language
from agent.core.llm_client import LLMUnavailable, generate_json

logger = logging.getLogger(__name__)


class NluResult(BaseModel):
    intent: Intent
    language: Language
    sentiment: float           # -1.0 (very angry) to +1.0 (very happy)
    wants_human: bool
    mentions_money: bool
    confidence: float          # 0.0 to 1.0


# ─────────────────────────────────────────────────────────────
# Keyword lists (case-insensitive, partial match)
# ─────────────────────────────────────────────────────────────

_KEYWORD_MAP: dict[Intent, list[str]] = {
    Intent.ASK_HUMAN: [
        "baat karao", "manager", "human", "insaan", "call karo", "kisi se baat",
        "supervisor", "incharge", "senior", "escalate", "real person",
        "speak to someone", "talk to someone", "connect me",
    ],
    Intent.ASK_FEES: [
        "fees", "fee", "charge", "kitna", "rental", "kitne ka", "price",
        "kitni", "paisa", "cost", "rate", "amount", "monthly", "kiraya",
        "mdr", "transaction charge", "upi charge",
    ],
    Intent.SETTLEMENT_QUERY: [
        "settlement", "paisa nahi aaya", "payment nahi aaya", "account mein nahi",
        "paise nahi mile", "credit nahi", "amount nahi", "nahi aaya",
        "nahi mila", "missing payment", "not received", "where is my money",
        "paise kab aayenge", "kab milega",
    ],
    Intent.ASK_DISCOUNT: [
        "discount", "kam karo", "free", "waive", "chhoot", "maafi",
        "reduce", "less fees", "no charge", "negotiate", "rebate", "wapas",
    ],
    Intent.COMPLAINT: [
        "bekar", "fraud", "dhokha", "band karo",
        "complain", "complaint", "problem", "issue", "cheating", "scam",
        "legal", "consumer forum", "chargeback", "refund",
    ],
    Intent.OPT_OUT: [
        "stop", "mat bhejo", "band karo messages", "unsubscribe",
        "do not contact", "remove me", "opt out", "no more messages",
        "mujhe message mat karo", "band karo",
    ],
    Intent.AGREE_VISIT: [
        "theek hai", "haan", "ok", "aa jao", "visit", "aa sakte ho",
        "kal aao", "schedule", "book", "confirm", "agreed", "yes",
        "sure", "fine by me", "okay",
    ],
    Intent.NOT_INTERESTED: [
        "nahi chahiye", "interested nahi", "not interested", "no thanks",
        "nahin", "mujhe nahi chahiye", "zaroorat nahi", "don't need",
        "cancel", "reject",
    ],
    Intent.SEND_DOCUMENT: [
        "photo bheja", "document bheja", "image send", "uploaded",
        "bhejta hun", "bheji", "sent", "here is", "yeh raha", "ye lo",
    ],
    Intent.DEVICE_ISSUE: [
        "device", "soundbox", "kaam nahi kar raha", "not working",
        "broken", "battery", "charging", "sound nahi", "announce nahi",
        "qr", "scan nahi", "wifi",
    ],
    Intent.GREETING: [
        "hello", "hi", "namaste", "namaskar", "hey", "good morning",
        "good evening", "jai hind", "hola", "sup", "bye", "alvida",
        "goodbye", "thank you", "thanks", "dhanyawad", "shukriya",
        "kaise ho", "kya haal", "kaisa hai",
    ],
    Intent.INTEREST: [
        "chahiye", "lena hai", "interested", "tell me more", "batao",
        "jankari chahiye", "details", "more info",
    ],
    Intent.ASK_DOCUMENTS: [
        "document", "kya chahiye", "what documents", "kaun se",
        "required", "pan", "aadhaar", "kyc", "papers",
    ],
}

_NEGATIVE_WORDS = [
    "fraud", "dhokha", "bekar", "scam", "cheating", "angry", "disgusting",
    "horrible", "worst", "terrible", "rubbish", "useless", "bakwaas", "ghatiya",
]

_POSITIVE_WORDS = [
    "thanks", "thank you", "shukriya", "dhanyawad", "good", "great", "excellent",
    "helpful", "nice", "wonderful", "appreciate", "happy", "satisfied",
]

_MONEY_WORDS = [
    "fees", "fee", "rupee", "paisa", "paise", "amount", "charge", "settlement",
    "payment", "money", "kitna", "cost", "price", "discount", "refund",
]

_HINDI_WORDS = [
    "hai", "hain", "nahi", "kya", "ka", "ki", "ke", "se", "mera", "tera",
    "aap", "main", "hum", "tum", "karo", "karo", "baat", "chahiye",
    "namaste", "theek", "acha",
]

_HINGLISH_WORDS = [
    "kar", "nahi", "ho", "raha", "mujhe", "aaya", "gaya", "lena", "dena",
    "tha", "thi", "wala", "wali", "bhi",
]


def _detect_language(text: str) -> Language:
    lower = text.lower()
    hindi_count = sum(1 for w in _HINDI_WORDS if w in lower.split())
    hinglish_count = sum(1 for w in _HINGLISH_WORDS if w in lower.split())
    # Check for Devanagari script
    if re.search(r"[\u0900-\u097F]", text):
        return Language.HINDI
    if hindi_count >= 2:
        return Language.HINDI
    if hindi_count >= 1 or hinglish_count >= 2:
        return Language.HINGLISH
    return Language.ENGLISH


def _sentiment(text: str) -> float:
    lower = text.lower()
    neg = sum(1 for w in _NEGATIVE_WORDS if w in lower)
    pos = sum(1 for w in _POSITIVE_WORDS if w in lower)
    raw = (pos - neg) / max(pos + neg, 1)
    return max(-1.0, min(1.0, float(raw)))


def _keyword_classify(text: str) -> tuple[Intent, float]:
    """
    Return (intent, confidence) from keyword matching.
    Nuanced, compound, or conversational questions receive moderate confidence (0.65)
    so that LLM classification evaluates the multi-clause context unless force_keywords is True.
    """
    lower = text.lower()
    words = text.strip().split()

    is_compound_or_conversational = (
        len(words) >= 6
        or any(conn in lower for conn in [" aur ", " and ", " lekin ", " but ", " ya ", " also ", " tatha ", " sath ", " saath "])
        or (lower.count("?") > 1)
    )

    # Priority check for explicit intents
    fast_intents: list[tuple[bool, Intent]] = [
        (any(w in lower for w in ["hello", "hi", "namaste", "namaskar", "hey", "good morning", "good evening", "bye", "alvida"]), Intent.GREETING),
        ("discount" in lower or "kam karo" in lower, Intent.ASK_DISCOUNT),
        ("fees" in lower or "fee" in lower or "charge" in lower or "kitna" in lower or "rental" in lower, Intent.ASK_FEES),
        ("settlement" in lower or "paisa nahi" in lower or "payment nahi" in lower, Intent.SETTLEMENT_QUERY),
        ("manager" in lower or "baat karao" in lower or "insaan" in lower, Intent.ASK_HUMAN),
        ("theek hai" in lower or "aa jao" in lower or "visit" in lower, Intent.AGREE_VISIT),
        ("stop" in lower or "mat bhejo" in lower or "unsubscribe" in lower, Intent.OPT_OUT),
    ]

    for condition, matched_intent in fast_intents:
        if condition:
            # If compound or conversational query, yield moderate confidence to let LLM evaluate nuance
            conf = 0.65 if is_compound_or_conversational else 0.95
            return matched_intent, conf

    matches: list[tuple[Intent, int]] = []

    for intent, keywords in _KEYWORD_MAP.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score > 0:
            matches.append((intent, score))

    if not matches:
        return Intent.OTHER, 0.0

    matches.sort(key=lambda x: x[1], reverse=True)
    top_intent, top_score = matches[0]

    if is_compound_or_conversational:
        confidence = 0.65
    elif len(matches) == 1 or matches[0][1] > matches[1][1]:
        confidence = min(0.95, 0.7 + top_score * 0.05)
    else:
        confidence = 0.6  # ambiguous — let LLM decide

    return top_intent, confidence


class _LLMNluInput(BaseModel):
    intent: str
    language: str
    sentiment: float
    wants_human: bool
    mentions_money: bool
    confidence: float


def _llm_classify(text: str, context_summary: str) -> NluResult | None:
    """Call the LLM for NLU. Returns None on failure."""
    from agent.prompts import nlu_prompt

    prompt = nlu_prompt.build(text=text, context_summary=context_summary)
    try:
        raw = generate_json(prompt, _LLMNluInput)
        intent_str = str(raw.intent).strip().lower()
        try:
            intent = Intent(intent_str)
        except ValueError:
            intent = Intent.OTHER

        lang_str = str(raw.language).strip().lower()
        try:
            lang = Language(lang_str)
        except ValueError:
            lang = Language.ENGLISH

        return NluResult(
            intent=intent,
            language=lang,
            sentiment=max(-1.0, min(1.0, float(raw.sentiment))),
            wants_human=bool(raw.wants_human),
            mentions_money=bool(raw.mentions_money),
            confidence=max(0.0, min(1.0, float(raw.confidence))),
        )
    except (LLMUnavailable, Exception) as exc:
        logger.warning("NLU LLM call failed, using keyword fallback: %s", exc)
        return None


def classify(
    text: str,
    context_summary: str = "",
    force_keywords: bool = False,
) -> NluResult:
    """
    Classify a merchant message.

    Args:
        text: The raw merchant text.
        context_summary: Brief context string for the LLM prompt.
        force_keywords: If True, skip the LLM entirely (used in tests).

    Returns:
        NluResult with intent, language, sentiment, wants_human, mentions_money, confidence.
    """
    if not text or not text.strip():
        return NluResult(
            intent=Intent.OTHER,
            language=Language.ENGLISH,
            sentiment=0.0,
            wants_human=False,
            mentions_money=False,
            confidence=1.0,
        )

    intent, kw_confidence = _keyword_classify(text)
    lang = _detect_language(text)
    sentiment = _sentiment(text)
    lower = text.lower()
    wants_human = intent == Intent.ASK_HUMAN or "manager" in lower or "baat karao" in lower
    mentions_money = any(w in lower for w in _MONEY_WORDS)

    # If keyword confidence is high enough, skip the LLM
    if force_keywords or kw_confidence >= 0.8:
        return NluResult(
            intent=intent,
            language=lang,
            sentiment=sentiment,
            wants_human=wants_human,
            mentions_money=mentions_money,
            confidence=kw_confidence,
        )

    # Try LLM for ambiguous / low-confidence cases
    llm_result = _llm_classify(text, context_summary)
    if llm_result:
        return llm_result

    # Fallback to keyword result
    return NluResult(
        intent=intent,
        language=lang,
        sentiment=sentiment,
        wants_human=wants_human,
        mentions_money=mentions_money,
        confidence=max(kw_confidence, 0.4),
    )

