"""Provider interfaces and shared JSON parsing helpers."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class ProviderError(RuntimeError):
    """Raised when the configured LLM provider fails."""


def extract_json_payload(raw_text: str) -> dict[str, Any]:
    """Parse a JSON object from raw model text, including fenced output."""

    candidate = raw_text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        candidate = "\n".join(line for line in lines if not line.startswith("```")).strip()

    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ProviderError("model did not return parseable JSON") from None
        try:
            payload = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ProviderError("model returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise ProviderError("model JSON root must be an object")
    return payload


class LLMProvider(ABC):
    """Abstract interface for structured LLM completions."""

    @abstractmethod
    async def complete_json(
        self,
        *,
        task_name: str,
        prompt: str,
        response_model: type[T],
        metadata: dict[str, Any] | None = None,
    ) -> T:
        """Generate structured JSON validated against a Pydantic model."""

    @staticmethod
    def validate_payload(response_model: type[T], payload: dict[str, Any]) -> T:
        """Validate a parsed JSON payload against the target response model."""

        try:
            return response_model.model_validate(payload)
        except ValidationError as exc:
            raise ProviderError(f"model JSON failed schema validation: {exc}") from exc
