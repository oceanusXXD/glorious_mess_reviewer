"""OpenAI Responses API provider implementation."""

from __future__ import annotations

import asyncio
from typing import Any, TypeVar

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI
from pydantic import BaseModel

from glorious_mess_reviewer.config.settings import Settings
from glorious_mess_reviewer.providers.base import LLMProvider, ProviderError, extract_json_payload

T = TypeVar("T", bound=BaseModel)


def _retry_delay_seconds(attempt: int) -> float:
    """Return the small linear backoff used between provider retries."""

    return 0.2 * attempt


def _is_retryable_status_error(exc: APIStatusError) -> bool:
    """Return whether an HTTP status error should be treated as transient."""

    status_code = getattr(exc, "status_code", None)
    return status_code is None or int(status_code) >= 500


def _raise_retry_error(exc: Exception, attempts: int) -> None:
    """Raise a consistent ProviderError once retry budget is exhausted."""

    if isinstance(exc, APITimeoutError):
        raise ProviderError(f"OpenAI API timed out after {attempts} attempt(s): {exc}") from exc
    if isinstance(exc, APIConnectionError):
        raise ProviderError(f"OpenAI API connection failed after {attempts} attempt(s): {exc}") from exc
    if isinstance(exc, APIStatusError):
        raise ProviderError(f"OpenAI API call failed after {attempts} attempt(s): {exc}") from exc
    raise ProviderError(f"unexpected OpenAI provider failure: {exc}") from exc


def _extract_parsed_response(response: Any) -> BaseModel:
    """Extract the parsed Pydantic payload from a Responses API object."""

    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            parsed = getattr(content, "parsed", None)
            if parsed is not None:
                return parsed
    raise ProviderError("OpenAI response did not contain parsed structured output")


class OpenAIResponsesProvider(LLMProvider):
    """Structured generation using the OpenAI Responses API."""

    def __init__(self, settings: Settings) -> None:
        """Create a provider backed by the configured OpenAI account."""

        if not settings.openai_api_key:
            raise ProviderError(
                "OPENAI_API_KEY or GLORIOUS_MESS_OPENAI_API_KEY is required for the OpenAI provider"
            )
        self._settings = settings
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=settings.request_timeout_seconds,
            max_retries=0,
        )

    async def complete_json(
        self,
        *,
        task_name: str,
        prompt: str,
        response_model: type[T],
        metadata: dict[str, Any] | None = None,
    ) -> T:
        """Call OpenAI and validate the JSON object returned by the model."""

        # 重试边界只覆盖 timeout / connection / 5xx；4xx 直接抛出，避免把确定性请求错误伪装成瞬时抖动。
        attempts = self._settings.provider_max_retries + 1
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                response = await self._client.responses.parse(
                    model=self._settings.default_model,
                    input=prompt,
                    text_format=response_model,
                    temperature=self._settings.default_temperature,
                )
                break
            except (APITimeoutError, APIConnectionError) as exc:
                last_error = exc
                if attempt >= attempts:
                    _raise_retry_error(exc, attempts)
                await asyncio.sleep(_retry_delay_seconds(attempt))
            except APIStatusError as exc:
                if not _is_retryable_status_error(exc):
                    raise ProviderError(f"OpenAI API call failed: {exc}") from exc
                last_error = exc
                if attempt >= attempts:
                    _raise_retry_error(exc, attempts)
                await asyncio.sleep(_retry_delay_seconds(attempt))
            except Exception as exc:
                _raise_retry_error(exc, attempts)
        else:  # pragma: no cover - defensive branch
            raise ProviderError(f"OpenAI provider exhausted retries: {last_error}")

        parsed = _extract_parsed_response(response)
        if hasattr(parsed, "model_dump"):
            return response_model.model_validate(parsed.model_dump(mode="json"))
        return response_model.model_validate(parsed)


class OpenAIChatCompletionsProvider(LLMProvider):
    """Structured generation through OpenAI-compatible chat completions."""

    def __init__(self, settings: Settings) -> None:
        """Create a provider for OpenAI-compatible chat-completion endpoints."""

        if not settings.openai_api_key:
            raise ProviderError(
                "OPENAI_API_KEY or GLORIOUS_MESS_OPENAI_API_KEY is required for the OpenAI-compatible chat provider"
            )
        self._settings = settings
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=settings.request_timeout_seconds,
            max_retries=0,
        )

    async def complete_json(
        self,
        *,
        task_name: str,
        prompt: str,
        response_model: type[T],
        metadata: dict[str, Any] | None = None,
    ) -> T:
        """Call a chat-completions endpoint and validate the returned JSON object."""

        attempts = self._settings.provider_max_retries + 1
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                response = await self._client.chat.completions.create(
                    model=self._settings.default_model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Return only one JSON object that matches the requested schema. "
                                "Do not include markdown fences or commentary."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=self._settings.default_temperature,
                )
                break
            except (APITimeoutError, APIConnectionError) as exc:
                last_error = exc
                if attempt >= attempts:
                    _raise_retry_error(exc, attempts)
                await asyncio.sleep(_retry_delay_seconds(attempt))
            except APIStatusError as exc:
                if not _is_retryable_status_error(exc):
                    raise ProviderError(f"OpenAI-compatible chat API call failed: {exc}") from exc
                last_error = exc
                if attempt >= attempts:
                    _raise_retry_error(exc, attempts)
                await asyncio.sleep(_retry_delay_seconds(attempt))
            except Exception as exc:
                _raise_retry_error(exc, attempts)
        else:  # pragma: no cover - defensive branch
            raise ProviderError(f"OpenAI-compatible chat provider exhausted retries: {last_error}")

        content = getattr(response.choices[0].message, "content", None)
        if not content:
            raise ProviderError("OpenAI-compatible chat response did not contain message content")
        payload = extract_json_payload(content)
        return self.validate_payload(response_model, payload)
