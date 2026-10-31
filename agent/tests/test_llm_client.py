from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from google import genai
from google.genai import types

from agent import settings
from agent.core.llm_client import _call_gemini, _safe_error_message


@pytest.mark.parametrize(
    ("json_mode", "expected_mime_type"),
    [(True, "application/json"), (False, "text/plain")],
)
def test_gemini_call_uses_timeout_response_mode_and_usage(
    monkeypatch: pytest.MonkeyPatch,
    json_mode: bool,
    expected_mime_type: str,
) -> None:
    response = SimpleNamespace(
        text='{"ok": true}' if json_mode else "hello",
        usage_metadata=SimpleNamespace(prompt_token_count=12, candidates_token_count=3),
    )
    models = Mock()
    models.generate_content.return_value = response
    client = Mock(models=models)
    client_factory = Mock(return_value=client)
    monkeypatch.setattr(genai, "Client", client_factory)
    monkeypatch.setattr(settings, "LLM_API_KEY", "test-api-key")
    monkeypatch.setattr(settings, "LLM_MODEL", "test-model")
    monkeypatch.setattr(settings, "LLM_TEMPERATURE", 0.25)

    content, usage = _call_gemini("test prompt", timeout_s=2.5, json_mode=json_mode)

    assert content == response.text
    assert usage == {"prompt_tokens": 12, "completion_tokens": 3}
    client_factory.assert_called_once()
    client_kwargs = client_factory.call_args.kwargs
    assert client_kwargs["api_key"] == "test-api-key"
    assert isinstance(client_kwargs["http_options"], types.HttpOptions)
    assert client_kwargs["http_options"].timeout == 2500
    generation = models.generate_content.call_args.kwargs
    assert generation["model"] == "test-model"
    assert generation["contents"] == "test prompt"
    assert generation["config"].response_mime_type == expected_mime_type
    assert generation["config"].temperature == 0.25
    client.close.assert_called_once()


def test_llm_error_message_redacts_configured_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LLM_API_KEY", "sensitive-test-key")

    message = _safe_error_message(RuntimeError("request failed with sensitive-test-key"))

    assert message == "request failed with [REDACTED]"
