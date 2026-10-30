"""
agent/core/llm_client.py — Thin, provider-agnostic LLM adapter.

Interface:
  generate_json(prompt, schema, timeout_s) -> BaseModel subclass instance
  generate_text(prompt, timeout_s) -> str

Features:
  - Timeout (default 15 seconds)
  - One automatic retry on transient failure
  - Schema validation via Pydantic
  - Response cache keyed by hash(prompt + model) — enable with LLM_CACHE=on
  - Logs latency and token counts
  - On failure raises LLMUnavailable; callers handle it gracefully

Supported providers: openai (default), anthropic, gemini.
The provider is selected via LLM_PROVIDER env var.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Type, TypeVar

from pydantic import BaseModel, ValidationError

from agent import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMUnavailable(Exception):
    """Raised when the LLM cannot be reached or returns an unusable response."""


# ── Response cache ────────────────────────────────────────────

_CACHE: dict[str, str] = {}


def _cache_key(prompt: str, model: str) -> str:
    return hashlib.sha256(f"{model}::{prompt}".encode()).hexdigest()


def _cache_get(key: str) -> str | None:
    return _CACHE.get(key) if settings.LLM_CACHE else None


def _cache_set(key: str, value: str) -> None:
    if settings.LLM_CACHE:
        _CACHE[key] = value


def _safe_error_message(error: Exception) -> str:
    message = str(error)
    if settings.LLM_API_KEY:
        message = message.replace(settings.LLM_API_KEY, "[REDACTED]")
    return message


# ── Provider dispatch ─────────────────────────────────────────

def _call_openai(prompt: str, timeout_s: float, json_mode: bool) -> tuple[str, dict]:
    """Call OpenAI Chat Completions API. Returns (content, usage)."""
    try:
        import openai  # type: ignore
    except ImportError:
        raise LLMUnavailable("openai package not installed. Run: pip install openai")

    client = openai.OpenAI(api_key=settings.LLM_API_KEY, timeout=timeout_s)
    kwargs: dict[str, Any] = {
        "model": settings.LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": settings.LLM_TEMPERATURE,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    resp = client.chat.completions.create(**kwargs)
    content = resp.choices[0].message.content or ""
    usage = {
        "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
        "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
    }
    return content, usage


def _call_anthropic(prompt: str, timeout_s: float, json_mode: bool) -> tuple[str, dict]:
    """Call Anthropic Messages API."""
    try:
        import anthropic  # type: ignore
    except ImportError:
        raise LLMUnavailable("anthropic package not installed. Run: pip install anthropic")

    client = anthropic.Anthropic(api_key=settings.LLM_API_KEY)
    resp = client.messages.create(
        model=settings.LLM_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    content = resp.content[0].text if resp.content else ""
    usage = {
        "prompt_tokens": resp.usage.input_tokens,
        "completion_tokens": resp.usage.output_tokens,
    }
    return content, usage


def _call_gemini(prompt: str, timeout_s: float, json_mode: bool) -> tuple[str, dict]:
    """Call Google Gemini API."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise LLMUnavailable("google-genai package not installed. Run: pip install google-genai")

    client = genai.Client(
        api_key=settings.LLM_API_KEY,
        http_options=types.HttpOptions(timeout=int(timeout_s * 1000)),
    )
    try:
        config = types.GenerateContentConfig(
            temperature=settings.LLM_TEMPERATURE,
            response_mime_type="application/json" if json_mode else "text/plain",
        )
        response = client.models.generate_content(
            model=settings.LLM_MODEL,
            contents=prompt,
            config=config,
        )
        content = response.text or ""
        usage_metadata = response.usage_metadata
        usage = {
            "prompt_tokens": usage_metadata.prompt_token_count if usage_metadata else 0,
            "completion_tokens": usage_metadata.candidates_token_count if usage_metadata else 0,
        }
        return content, usage
    finally:
        client.close()


_PROVIDERS: dict[str, Any] = {
    "openai": _call_openai,
    "anthropic": _call_anthropic,
    "gemini": _call_gemini,
}


def _call_llm(prompt: str, timeout_s: float, json_mode: bool) -> tuple[str, dict]:
    """Dispatch to the configured provider."""
    provider = settings.LLM_PROVIDER.lower()
    fn = _PROVIDERS.get(provider)
    if not fn:
        raise LLMUnavailable(f"Unknown LLM provider: {provider!r}")
    return fn(prompt, timeout_s, json_mode)


# ── Public API ────────────────────────────────────────────────

def generate_json(
    prompt: str,
    schema: Type[T],
    timeout_s: float | None = None,
) -> T:
    """
    Call the LLM and parse the response as the given Pydantic schema.

    Retries once on transient failure.
    Raises LLMUnavailable if both attempts fail.
    """
    timeout_s = timeout_s or settings.LLM_TIMEOUT_SECONDS
    key = _cache_key(prompt, settings.LLM_MODEL)
    cached = _cache_get(key)

    if cached:
        try:
            return schema.model_validate_json(cached)
        except (ValidationError, ValueError):
            pass

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            t0 = time.perf_counter()
            content, usage = _call_llm(prompt, timeout_s, json_mode=True)
            latency_ms = int((time.perf_counter() - t0) * 1000)
            logger.info(
                "LLM call attempt=%d latency=%dms prompt_tokens=%s completion_tokens=%s",
                attempt + 1,
                latency_ms,
                usage.get("prompt_tokens", "?"),
                usage.get("completion_tokens", "?"),
            )
            # Extract JSON if wrapped in markdown
            json_str = _extract_json(content)
            result = schema.model_validate_json(json_str)
            _cache_set(key, json_str)
            return result
        except (LLMUnavailable, ValidationError, ValueError, Exception) as exc:
            last_error = exc
            logger.warning("LLM attempt %d failed: %s", attempt + 1, _safe_error_message(exc))
            if attempt == 0:
                time.sleep(0.5)

    error_message = _safe_error_message(last_error) if last_error else "Unknown failure"
    raise LLMUnavailable(f"LLM unavailable after 2 attempts: {error_message}")


def generate_text(prompt: str, timeout_s: float | None = None) -> str:
    """
    Call the LLM and return the raw text response.

    Retries once on transient failure.
    Raises LLMUnavailable if both attempts fail.
    """
    timeout_s = timeout_s or settings.LLM_TIMEOUT_SECONDS
    key = _cache_key(prompt + ":text", settings.LLM_MODEL)
    cached = _cache_get(key)
    if cached:
        return cached

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            t0 = time.perf_counter()
            content, usage = _call_llm(prompt, timeout_s, json_mode=False)
            latency_ms = int((time.perf_counter() - t0) * 1000)
            logger.info("LLM text call attempt=%d latency=%dms", attempt + 1, latency_ms)
            _cache_set(key, content)
            return content
        except Exception as exc:
            last_error = exc
            logger.warning("LLM text attempt %d failed: %s", attempt + 1, _safe_error_message(exc))
            if attempt == 0:
                time.sleep(0.5)

    error_message = _safe_error_message(last_error) if last_error else "Unknown failure"
    raise LLMUnavailable(f"LLM unavailable after 2 attempts: {error_message}")


def _extract_json(content: str) -> str:
    """Strip markdown code fences if present."""
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        # Remove first and last fence lines
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        content = "\n".join(inner).strip()
    return content
