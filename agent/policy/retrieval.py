"""
agent/policy/retrieval.py — BM25-based policy document retrieval.

Splits policy docs by heading, ranks with BM25, returns top-k passages.
Includes a Hindi synonym map for common query terms.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from agent import settings

# ── Optional BM25 dependency ──────────────────────────────────
try:
    from rank_bm25 import BM25Okapi  # type: ignore
    _HAS_BM25 = True
except ImportError:
    _HAS_BM25 = False


@dataclass
class PolicyPassage:
    source: str      # filename + heading, e.g. "fees.md > Soundbox Rental"
    text: str
    score: float


# ── Hindi / Hinglish synonym map ──────────────────────────────
_SYNONYMS: dict[str, list[str]] = {
    "ask_fees": ["fee", "fees", "charge", "charges", "rental", "rent", "cost", "price"],
    "ask_documents": ["document", "documents", "kyc", "pan", "aadhaar", "identity", "papers"],
    "device_issue": ["device", "soundbox", "speaker", "machine", "broken", "repair", "charging"],
    "kitna": ["fee", "charge", "price", "cost", "amount", "rental"],
    "kitne": ["fee", "charge", "price", "cost"],
    "kitni": ["fee", "charge", "price"],
    "fees": ["fee", "charge", "rental"],
    "charge": ["fee", "charge", "rental"],
    "charges": ["fee", "charge", "rental"],
    "extra": ["additional", "charge", "charges", "fee"],
    "monthly": ["month", "rental", "rent", "recurring"],
    "kiraya": ["rental", "rent", "monthly", "fee"],
    "cut": ["deducted", "deduction", "charge", "fee"],
    "upi": ["upi", "payment", "transaction"],
    "transaction": ["transaction", "payment", "upi", "charge"],
    "transactions": ["transaction", "payment", "upi", "charge"],
    "payment": ["payment", "transaction", "upi", "charge"],
    "rental": ["rental", "fee", "monthly", "rent"],
    "settlement": ["settlement", "payment", "paise", "credit", "account"],
    "paisa": ["payment", "amount", "settlement", "money"],
    "paise": ["payment", "amount", "settlement", "money"],
    "nahi": ["not", "no", "missing", "failed"],
    "aaya": ["received", "credited", "arrived", "came"],
    "nahi_aaya": ["not received", "missing", "not credited"],
    "kyc": ["kyc", "document", "verification", "pan", "identity"],
    "soundbox": ["soundbox", "device", "speaker", "qr"],
    "device": ["device", "soundbox", "machine"],
    "discount": ["discount", "waiver", "reduce", "less", "free"],
    "baat": ["talk", "speak", "human", "manager", "person"],
    "manager": ["manager", "supervisor", "human", "support"],
}


def _expand_query(query: str) -> list[str]:
    """Expand query tokens with synonyms for better Hindi/Hinglish recall."""
    tokens = re.findall(r"\w+", query.lower())
    expanded: list[str] = []
    for token in tokens:
        expanded.append(token)
        if token in _SYNONYMS:
            expanded.extend(_SYNONYMS[token])
    return expanded


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer."""
    return re.findall(r"\w+", text.lower())


def _load_passages(docs_dir: Path) -> list[tuple[str, str]]:
    """
    Load all policy documents and split by heading.
    Returns list of (source_label, passage_text).
    """
    passages: list[tuple[str, str]] = []
    for md_file in sorted(docs_dir.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        filename = md_file.name

        # Split on headings (## or ###)
        sections = re.split(r"\n(?=#{2,3}\s)", content)
        for section in sections:
            section = section.strip()
            if not section or len(section) < 30:
                continue
            # Extract heading for the source label
            heading_match = re.match(r"^#{2,3}\s+(.+?)$", section, re.MULTILINE)
            heading = heading_match.group(1).strip() if heading_match else "General"
            source = f"{filename} > {heading}"
            passages.append((source, section))

    return passages


class PolicyRetrieval:
    """
    BM25-based retrieval over policy markdown documents.
    Falls back to simple keyword overlap if rank_bm25 is not installed.
    """

    _docs_dir: Path = Path(__file__).parent / "docs"

    def __init__(self, docs_dir: Path | None = None) -> None:
        self._dir = docs_dir or self._docs_dir
        self._passages: list[tuple[str, str]] = []
        self._tokenized: list[list[str]] = []
        self._bm25: object | None = None
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._passages = _load_passages(self._dir)
        self._tokenized = [_tokenize(text) for _, text in self._passages]
        if _HAS_BM25 and self._tokenized:
            self._bm25 = BM25Okapi(self._tokenized)
        self._loaded = True

    def search(self, query: str, language: str = "english") -> list[PolicyPassage]:
        """
        Search policy documents for passages relevant to the query.

        Returns up to POLICY_TOP_K passages with score >= POLICY_BM25_THRESHOLD.
        Returns an empty list when nothing matches — callers should escalate.
        """
        self._ensure_loaded()
        if not self._passages:
            return []

        expanded = _expand_query(query)

        if self._bm25 is not None:
            scores: list[float] = list(self._bm25.get_scores(expanded))
        else:
            # Fallback: simple overlap count
            query_tokens = set(expanded)
            scores = [
                sum(1 for t in tokens if t in query_tokens) / max(len(tokens), 1)
                for tokens in self._tokenized
            ]

        # Rank and filter
        indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        results: list[PolicyPassage] = []
        for idx, score in indexed[: settings.POLICY_TOP_K]:
            if score < settings.POLICY_BM25_THRESHOLD:
                break
            source, text = self._passages[idx]
            results.append(PolicyPassage(source=source, text=text, score=round(score, 4)))

        return results

    def reload(self) -> None:
        """Force a reload of policy documents (useful in tests)."""
        self._loaded = False
        self._ensure_loaded()


# Module-level singleton
_retrieval: PolicyRetrieval | None = None


def get_retrieval(docs_dir: Path | None = None) -> PolicyRetrieval:
    global _retrieval
    if _retrieval is None or docs_dir is not None:
        _retrieval = PolicyRetrieval(docs_dir)
    return _retrieval


def search_policy(query: str, language: str = "english") -> list[PolicyPassage]:
    """Convenience function using the module-level singleton."""
    return get_retrieval().search(query, language)
