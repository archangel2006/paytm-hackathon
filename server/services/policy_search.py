import os
import re
from typing import List, Dict, Any, Optional

HINDI_SYNONYMS = {
    "fees": ["fee", "charge", "rental", "kitna", "kiraya", "rate", "cost", "price", "soundbox"],
    "settlement": ["settle", "paisa", "payment", "khata", "account", "credit", "holiday", "bank"],
    "kyc": ["document", "pan", "aadhar", "proof", "photo", "blurry", "dastavej"],
    "device": ["soundbox", "battery", "light", "sim", "network", "volume", "awaz", "red", "blue"]
}

class PolicySearchService:
    def __init__(self, docs_dir: Optional[str] = None):
        if not docs_dir:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            docs_dir = os.path.join(base_dir, "docs", "policies")
        self.docs_dir = docs_dir
        self.sections: List[Dict[str, Any]] = []
        self._load_documents()

    def _load_documents(self):
        self.sections = []
        if not os.path.exists(self.docs_dir):
            return

        for fname in os.listdir(self.docs_dir):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(self.docs_dir, fname)
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Split into sections by Markdown headings
            parts = re.split(r"\n(?=##\s+)", content)
            doc_title = fname
            first_h1 = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            if first_h1:
                doc_title = first_h1.group(1).strip()

            for part in parts:
                part = part.strip()
                if not part:
                    continue
                heading_match = re.search(r"^##\s+(.+)$", part, re.MULTILINE)
                heading = heading_match.group(1).strip() if heading_match else "Overview"
                body = re.sub(r"^##\s+.+$", "", part, flags=re.MULTILINE).strip()

                self.sections.append({
                    "file": fname,
                    "doc_title": doc_title,
                    "heading": heading,
                    "source": f"{fname}#{heading}",
                    "text": part,
                    "body": body
                })

    def search(self, query: str, top_k: int = 3, min_score: float = 0.5) -> List[Dict[str, Any]]:
        if not self.sections:
            self._load_documents()

        query_tokens = [w.lower() for w in re.findall(r"\w+", query) if len(w) > 1]
        if not query_tokens:
            return []

        # Expand query tokens with synonyms
        expanded_tokens = set(query_tokens)
        for q in query_tokens:
            for canon, syns in HINDI_SYNONYMS.items():
                if q in syns or q == canon:
                    expanded_tokens.add(canon)
                    expanded_tokens.update(syns)

        scored_sections = []
        for sec in self.sections:
            text_lower = (sec["heading"] + " " + sec["body"]).lower()
            heading_lower = sec["heading"].lower()

            score = 0.0
            for token in expanded_tokens:
                # Higher weight if token appears in heading
                if token in heading_lower:
                    score += 3.0
                if token in text_lower:
                    score += 1.0

            if score > 0:
                # Normalize score
                normalized = score / (len(query_tokens) + 1.0)
                scored_sections.append({
                    "source": sec["source"],
                    "file": sec["file"],
                    "doc_title": sec["doc_title"],
                    "heading": sec["heading"],
                    "text": sec["body"],
                    "score": round(normalized, 2)
                })

        scored_sections.sort(key=lambda x: x["score"], reverse=True)
        results = [s for s in scored_sections if s["score"] >= min_score][:top_k]
        return results

policy_search_service = PolicySearchService()

