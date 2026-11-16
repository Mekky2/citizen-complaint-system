"""NvidiaNimClient with the OpenAI SDK mocked. These tests prove configuration, error mapping and
secret hygiene. They do NOT prove that the real NVIDIA endpoint works (see tests/integration/
test_nim_live.py, which needs a real key)."""

import logging
from types import SimpleNamespace

import httpx
import openai
import pytest

from app.agents.complaint_agent import nim_client, run_complaint_agent
from app.agents.complaint_agent.nim_client import (
    LLMConfigError,
    LLMProviderError,
    NvidiaNimClient,
    build_llm_client,
)
from app.core.config import Settings
from tests.unit.complaint_agent.fakes import FakeRag, make_state

SECRET = "nvapi-SECRET-KEY-123"
REQ = httpx.Request("POST", "https://integrate.api.nvidia.com/v1/chat/completions")


def _resp(code: int) -> httpx.Response:
    return httpx.Response(code, request=REQ)


def _completion(content):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class FakeOpenAI:
    """Stands in for openai.OpenAI: returns / raises the scripted items in order."""

    def __init__(self, *script):
        self.script = list(script)
        self.requests: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def make_client(fake) -> NvidiaNimClient:
    return NvidiaNimClient(api_key=SECRET, model="m", base_url="http://x", client=fake)


# --- configuration -------------------------------------------------------------------
def test_settings_defaults_match_the_decision():
    s = Settings(_env_file=None)
    assert s.llm_provider == "nvidia_nim"
    assert s.llm_model == "mistralai/mistral-large-4-1t-a52b"
    assert s.llm_base_url == "https://integrate.api.nvidia.com/v1"
    assert s.llm_timeout_seconds == 120


def test_build_client_passes_configuration_to_openai_sdk(monkeypatch):
    captured = {}

    class Spy:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=None))

    monkeypatch.setattr(nim_client.openai, "OpenAI", Spy)
    settings = Settings(_env_file=None, llm_api_key=SECRET)
    build_llm_client(settings)
    assert captured == {
        "api_key": SECRET,
        "base_url": "https://integrate.api.nvidia.com/v1",
        "timeout": float(settings.llm_timeout_seconds),
        "max_retries": 0,  # retries belong to the Orchestrator
    }


@pytest.mark.parametrize("key", ["", "changeme", "  ChangeMe  ", "your-nvidia-nim-api-key"])
def test_missing_or_placeholder_key_is_a_config_error(key):
    with pytest.raises(LLMConfigError) as err:
        build_llm_client(Settings(_env_file=None, llm_api_key=key))
    assert "LLM_API_KEY" in str(err.value)


def test_unsupported_provider_is_a_config_error():
    with pytest.raises(LLMConfigError):
        build_llm_client(Settings(_env_file=None, llm_provider="other", llm_api_key=SECRET))


def test_config_errors_never_contain_the_key():
    # real-looking key + unsupported provider: the error must not echo the key
    with pytest.raises(LLMConfigError) as err:
        build_llm_client(Settings(_env_file=None, llm_provider="other", llm_api_key=SECRET))
    assert SECRET not in str(err.value)
    # placeholder key: the error names the variable, not its value
    with pytest.raises(LLMConfigError) as err2:
        build_llm_client(Settings(_env_file=None, llm_api_key="changeme"))
    assert "changeme" not in str(err2.value)


# --- request / response -------------------------------------------------------------------
def test_request_uses_model_messages_and_deterministic_settings():
    fake = FakeOpenAI(_completion('{"ok": true}'))
    client = NvidiaNimClient(api_key=SECRET, model="my-model", base_url="http://x", client=fake)
    assert client.complete("SYS", "USER") == '{"ok": true}'
    req = fake.requests[0]
    assert req["model"] == "my-model" and req["temperature"] == 0
    assert req["messages"] == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "USER"},
    ]


def test_arabic_text_is_sent_unchanged():
    fake = FakeOpenAI(_completion("{}"))
    make_client(fake).complete("s", "ماسورة المية مكسورة")
    assert fake.requests[0]["messages"][1]["content"] == "ماسورة المية مكسورة"


@pytest.mark.parametrize(
    "bad",
    [
        SimpleNamespace(choices=[]),
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=None))]),
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=123))]),
        SimpleNamespace(),
        None,
    ],
)
def test_empty_or_odd_responses_return_empty_string(bad):
    assert make_client(FakeOpenAI(bad)).complete("s", "u") == ""


# --- provider errors ---------------------------------------------------------------------
@pytest.mark.parametrize(
    ("error", "transient", "status"),
    [
        (openai.APITimeoutError(request=REQ), True, None),
        (openai.APIConnectionError(request=REQ), True, None),
        (openai.RateLimitError("rate", response=_resp(429), body=None), True, 429),
        (openai.InternalServerError("boom", response=_resp(503), body=None), True, 503),
        (openai.AuthenticationError("bad key", response=_resp(401), body=None), False, 401),
        (openai.BadRequestError("bad", response=_resp(400), body=None), False, 400),
        (RuntimeError("unexpected sdk bug"), False, None),
    ],
)
def test_provider_errors_are_wrapped_with_transient_flag(error, transient, status):
    with pytest.raises(LLMProviderError) as err:
        make_client(FakeOpenAI(error)).complete("s", "u")
    assert err.value.transient is transient and err.value.status_code == status


def test_errors_and_logs_never_expose_key_or_complaint_text(caplog):
    leaky = openai.AuthenticationError(
        f"invalid key {SECRET} for request about Ahmed Ali", response=_resp(401), body=None
    )
    with caplog.at_level(logging.DEBUG), pytest.raises(LLMProviderError) as err:
        make_client(FakeOpenAI(leaky)).complete("system", "complaint from Ahmed Ali 29812345678901")
    visible = str(err.value) + caplog.text
    for secret in (SECRET, "Ahmed", "29812345678901"):
        assert secret not in visible


# --- through the agent ---------------------------------------------------------------------
def test_agent_runs_end_to_end_on_mocked_sdk():
    fake = FakeOpenAI(
        _completion('{"category": "Water"}'),
        _completion('{"severity": "Critical", "confidence": "high"}'),
        _completion('{"recommendations": [{"text": "Repair within 24 hours", "source_ids": [1]}]}'),
        _completion('{"verdicts": [{"index": 1, "supported": true}]}'),
    )
    out = run_complaint_agent(make_state(), make_client(fake), FakeRag())
    assert out["status"] == "Completed" and out["tool_calls"] == 5
    assert len(fake.requests) == 4


@pytest.mark.parametrize(
    ("script", "reason"),
    [
        ([openai.APITimeoutError(request=REQ)], "LLM_PROVIDER_ERROR"),
        ([openai.AuthenticationError("x", response=_resp(401), body=None)], "LLM_PROVIDER_ERROR"),
        ([_completion("")], "MALFORMED_LLM_RESPONSE"),
        ([_completion("Sorry, I cannot help")], "MALFORMED_LLM_RESPONSE"),
        ([_completion(None)], "MALFORMED_LLM_RESPONSE"),
    ],
)
def test_agent_turns_provider_problems_into_failed_payload(script, reason):
    out = run_complaint_agent(make_state(), make_client(FakeOpenAI(*script)), FakeRag())
    assert out["status"] == "Failed" and out["failure_reason"] == reason
