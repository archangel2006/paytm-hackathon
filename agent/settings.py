"""
agent/settings.py — Thresholds, limits, and weights for the agent.

All values can be overridden via environment variables.
Never hardcode these in business logic — always import from here.
"""
import os
from pathlib import Path


def _load_local_env() -> None:
    """Load local environment files without overwriting process variables."""
    candidates = (
        Path(__file__).with_name(".env"),
        Path(__file__).parent.parent / "integrations" / ".env",
        Path(__file__).parent.parent / ".env",
        Path.cwd() / ".env",
    )
    for path in candidates:
        if not path.is_file():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = value
        break


_load_local_env()


# ── Retry limits ──────────────────────────────────────────────
MAX_CONTACT_ATTEMPTS: int = int(os.getenv("MAX_CONTACT_ATTEMPTS", "3"))
MAX_ACTIVATION_NUDGES: int = int(os.getenv("MAX_ACTIVATION_NUDGES", "2"))
MAX_DOC_REREQUESTS: int = int(os.getenv("MAX_DOC_REREQUESTS", "2"))
# Set to 0 (or a negative value) to disable the daily outbound limit.
MAX_MESSAGES_PER_DAY: int = int(os.getenv("MAX_MESSAGES_PER_DAY", "3"))

# ── Quiet hours (24-hour clock, local timezone) ───────────────
QUIET_HOUR_START: int = int(os.getenv("QUIET_HOUR_START", "21"))   # 21:00
QUIET_HOUR_END: int = int(os.getenv("QUIET_HOUR_END", "8"))         # 08:00

# ── Planner / NLU ─────────────────────────────────────────────
MIN_PLANNER_CONFIDENCE: float = float(os.getenv("MIN_PLANNER_CONFIDENCE", "0.6"))
LLM_TIMEOUT_SECONDS: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "15.0"))
LLM_CACHE: bool = os.getenv("LLM_CACHE", "off").lower() == "on"
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))

# ── Guardrails ────────────────────────────────────────────────
SENTIMENT_ESCALATE_THRESHOLD: float = float(os.getenv("SENTIMENT_ESCALATE_THRESHOLD", "-0.5"))

# ── Lead scoring weights ──────────────────────────────────────
SCORE_WEIGHT_FOOTFALL: float = float(os.getenv("SCORE_WEIGHT_FOOTFALL", "0.30"))
SCORE_WEIGHT_CATEGORY: float = float(os.getenv("SCORE_WEIGHT_CATEGORY", "0.25"))
SCORE_WEIGHT_ENGAGEMENT: float = float(os.getenv("SCORE_WEIGHT_ENGAGEMENT", "0.20"))
SCORE_WEIGHT_RESPONSIVENESS: float = float(os.getenv("SCORE_WEIGHT_RESPONSIVENESS", "0.15"))
SCORE_WEIGHT_PROXIMITY: float = float(os.getenv("SCORE_WEIGHT_PROXIMITY", "0.10"))

# ── Policy retrieval ──────────────────────────────────────────
POLICY_BM25_THRESHOLD: float = float(os.getenv("POLICY_BM25_THRESHOLD", "0.1"))
POLICY_TOP_K: int = int(os.getenv("POLICY_TOP_K", "3"))

# ── Visit scheduling ──────────────────────────────────────────
VISIT_NEARBY_RADIUS_KM: float = float(os.getenv("VISIT_NEARBY_RADIUS_KM", "2.0"))
VISIT_SLOT_DURATION_MINUTES: int = int(os.getenv("VISIT_SLOT_DURATION_MINUTES", "45"))
VISIT_START_HOUR: int = int(os.getenv("VISIT_START_HOUR", "11"))

# ── Timers ────────────────────────────────────────────────────
TIMER_ACTIVATION_CHECK_HOURS: int = int(os.getenv("TIMER_ACTIVATION_CHECK_HOURS", "24"))
TIMER_FOLLOWUP_DAYS: int = int(os.getenv("TIMER_FOLLOWUP_DAYS", "2"))
TIMER_SETTLEMENT_RECHECK_EXTRA_HOURS: int = int(os.getenv("TIMER_SETTLEMENT_RECHECK_EXTRA_HOURS", "2"))
TIMER_DOCS_REMINDER_DAYS: int = int(os.getenv("TIMER_DOCS_REMINDER_DAYS", "1"))

# ── Dormant cooldown ──────────────────────────────────────────
DORMANT_COOLDOWN_DAYS: int = int(os.getenv("DORMANT_COOLDOWN_DAYS", "7"))

# ── Prompt versioning ─────────────────────────────────────────
PROMPT_VERSION: str = os.getenv("PROMPT_VERSION", "v1")
