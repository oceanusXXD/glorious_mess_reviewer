"""Deterministic provider for tests and local fixtures."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from glorious_mess_reviewer.providers.base import LLMProvider, ProviderError, extract_json_payload

T = TypeVar("T", bound=BaseModel)


class MockLLMProvider(LLMProvider):
    """Return pre-registered outputs keyed by manuscript and task name."""

    def __init__(self, registry: dict[tuple[str, str], dict[str, Any] | str]) -> None:
        """Create a provider from a deterministic registry."""

        self._registry = registry

    async def complete_json(
        self,
        *,
        task_name: str,
        prompt: str,
        response_model: type[T],
        metadata: dict[str, Any] | None = None,
    ) -> T:
        """Return a deterministic payload without calling a real LLM."""

        manuscript_id = (metadata or {}).get("manuscript_id")
        key = (manuscript_id, task_name)
        if key not in self._registry:
            if not self._registry:
                raise ProviderError(
                    "MockLLMProvider is test-only unless fixture responses are injected. "
                    "Use dry-run, configure OpenAI, or inject a fixture-backed MockLLMProvider."
                )
            raise ProviderError(f"mock registry missing response for {key}")

        payload = self._registry[key]
        if isinstance(payload, str):
            parsed = extract_json_payload(payload)
        else:
            parsed = payload
        return self.validate_payload(response_model, parsed)
