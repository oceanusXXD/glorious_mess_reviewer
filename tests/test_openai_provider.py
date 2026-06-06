"""OpenAI provider retry behavior tests."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError

from glorious_mess_reviewer.config import Settings
from glorious_mess_reviewer.providers import ProviderError
from glorious_mess_reviewer.providers.openai_provider import OpenAIChatCompletionsProvider, OpenAIResponsesProvider
from glorious_mess_reviewer.schemas import PrecheckDecision, PrecheckOutput


@pytest.fixture(autouse=True)
def _disable_retry_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fast_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("glorious_mess_reviewer.providers.openai_provider.asyncio.sleep", _fast_sleep)


@pytest.fixture(autouse=True)
def _fake_async_openai_client(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeAsyncOpenAI:
        def __init__(self, **kwargs: object) -> None:
            self.api_key = kwargs.get("api_key")
            self.base_url = kwargs.get("base_url")
            self.timeout = kwargs.get("timeout")
            self.max_retries = kwargs.get("max_retries")
            self.responses = SimpleNamespace(parse=None)

    monkeypatch.setattr("glorious_mess_reviewer.providers.openai_provider.AsyncOpenAI", _FakeAsyncOpenAI)


def _fake_parsed_response(payload: PrecheckOutput):
    return SimpleNamespace(
        output=[
            SimpleNamespace(
                content=[SimpleNamespace(parsed=payload)]
            )
        ]
    )


def test_openai_provider_disables_sdk_internal_retries() -> None:
    settings = Settings(openai_api_key="test-key", provider_max_retries=0)

    provider = OpenAIResponsesProvider(settings)

    assert provider._client.max_retries == 0


@pytest.mark.asyncio
async def test_openai_responses_provider_omits_optional_metadata_for_compatible_endpoints() -> None:
    settings = Settings(openai_api_key="test-key", provider_max_retries=0)
    provider = OpenAIResponsesProvider(settings)

    async def fake_parse(**kwargs: object):
        assert "metadata" not in kwargs
        return _fake_parsed_response(
            PrecheckOutput(
                decision=PrecheckDecision.PASS,
                minimum_reviewable=True,
                hard_failures=[],
                missing_sections=[],
                risk_flags=[],
                notes=[],
            )
        )

    provider._client = SimpleNamespace(responses=SimpleNamespace(parse=fake_parse))

    result = await provider.complete_json(
        task_name="HanCeGateAgent",
        prompt="{}",
        response_model=PrecheckOutput,
        metadata={"manuscript_id": "fixture-001"},
    )

    assert result.minimum_reviewable is True


@pytest.mark.asyncio
async def test_openai_provider_retries_transient_connection_errors() -> None:
    settings = Settings(openai_api_key="test-key", provider_max_retries=1)
    provider = OpenAIResponsesProvider(settings)
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    calls = {"count": 0}

    async def fake_parse(**_: object):
        calls["count"] += 1
        if calls["count"] == 1:
            raise APIConnectionError(message="boom", request=request)
        return _fake_parsed_response(
            PrecheckOutput(
                decision=PrecheckDecision.PASS,
                minimum_reviewable=True,
                hard_failures=[],
                missing_sections=[],
                risk_flags=[],
                notes=[],
            )
        )

    provider._client = SimpleNamespace(responses=SimpleNamespace(parse=fake_parse))
    result = await provider.complete_json(
        task_name="HanCeGateAgent",
        prompt="{}",
        response_model=PrecheckOutput,
    )
    assert result.minimum_reviewable is True
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_openai_provider_retries_transient_timeouts() -> None:
    settings = Settings(openai_api_key="test-key", provider_max_retries=1)
    provider = OpenAIResponsesProvider(settings)
    calls = {"count": 0}

    async def fake_parse(**_: object):
        calls["count"] += 1
        if calls["count"] == 1:
            raise APITimeoutError(request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
        return _fake_parsed_response(
            PrecheckOutput(
                decision=PrecheckDecision.PASS,
                minimum_reviewable=True,
                hard_failures=[],
                missing_sections=[],
                risk_flags=[],
                notes=[],
            )
        )

    provider._client = SimpleNamespace(responses=SimpleNamespace(parse=fake_parse))
    result = await provider.complete_json(
        task_name="HanCeGateAgent",
        prompt="{}",
        response_model=PrecheckOutput,
    )
    assert result.minimum_reviewable is True
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_openai_provider_does_not_retry_non_retryable_status_errors() -> None:
    settings = Settings(openai_api_key="test-key", provider_max_retries=2)
    provider = OpenAIResponsesProvider(settings)
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    response = httpx.Response(status_code=400, request=request)
    calls = {"count": 0}

    async def fake_parse(**_: object):
        calls["count"] += 1
        raise APIStatusError("bad request", response=response, body=None)

    provider._client = SimpleNamespace(responses=SimpleNamespace(parse=fake_parse))
    with pytest.raises(ProviderError):
        await provider.complete_json(
            task_name="HanCeGateAgent",
            prompt="{}",
            response_model=PrecheckOutput,
        )
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_openai_provider_retries_retryable_status_errors() -> None:
    settings = Settings(openai_api_key="test-key", provider_max_retries=1)
    provider = OpenAIResponsesProvider(settings)
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    response = httpx.Response(status_code=503, request=request)
    calls = {"count": 0}

    async def fake_parse(**_: object):
        calls["count"] += 1
        if calls["count"] == 1:
            raise APIStatusError("temporarily unavailable", response=response, body=None)
        return _fake_parsed_response(
            PrecheckOutput(
                decision=PrecheckDecision.PASS,
                minimum_reviewable=True,
                hard_failures=[],
                missing_sections=[],
                risk_flags=[],
                notes=[],
            )
        )

    provider._client = SimpleNamespace(responses=SimpleNamespace(parse=fake_parse))
    result = await provider.complete_json(
        task_name="HanCeGateAgent",
        prompt="{}",
        response_model=PrecheckOutput,
    )
    assert result.minimum_reviewable is True
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_openai_provider_raises_after_retry_exhaustion() -> None:
    settings = Settings(openai_api_key="test-key", provider_max_retries=1)
    provider = OpenAIResponsesProvider(settings)
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    calls = {"count": 0}

    async def fake_parse(**_: object):
        calls["count"] += 1
        raise APIConnectionError(message="still broken", request=request)

    provider._client = SimpleNamespace(responses=SimpleNamespace(parse=fake_parse))
    with pytest.raises(ProviderError, match=r"connection failed after 2 attempt\(s\)"):
        await provider.complete_json(
            task_name="HanCeGateAgent",
            prompt="{}",
            response_model=PrecheckOutput,
        )
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_openai_provider_rejects_missing_parsed_structured_output() -> None:
    settings = Settings(openai_api_key="test-key")
    provider = OpenAIResponsesProvider(settings)

    async def fake_parse(**_: object):
        return SimpleNamespace(output=[SimpleNamespace(content=[SimpleNamespace(parsed=None)])])

    provider._client = SimpleNamespace(responses=SimpleNamespace(parse=fake_parse))
    with pytest.raises(ProviderError, match="did not contain parsed structured output"):
        await provider.complete_json(
            task_name="HanCeGateAgent",
            prompt="{}",
            response_model=PrecheckOutput,
        )


@pytest.mark.asyncio
async def test_openai_chat_provider_parses_json_content() -> None:
    settings = Settings(openai_api_key="test-key", openai_api_style="chat_completions")
    provider = OpenAIChatCompletionsProvider(settings)
    calls = {"count": 0}

    async def fake_create(**kwargs: object):
        calls["count"] += 1
        assert kwargs["response_format"] == {"type": "json_object"}
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"decision":"pass","minimum_reviewable":true,"hard_failures":[],"missing_sections":[],"risk_flags":[],"notes":[]}'
                    )
                )
            ]
        )

    provider._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create)))

    result = await provider.complete_json(
        task_name="HanCeGateAgent",
        prompt="Return JSON.",
        response_model=PrecheckOutput,
    )

    assert result.decision is PrecheckDecision.PASS
    assert result.minimum_reviewable is True
    assert calls["count"] == 1
