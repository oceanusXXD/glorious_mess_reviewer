"""Base class for provider-backed review panel workers."""

from __future__ import annotations

import json
from abc import ABC
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from glorious_mess_reviewer.prompts.few_shots import build_venue_examples_text
from glorious_mess_reviewer.prompts import PromptTemplate, render_prompt
from glorious_mess_reviewer.prompts.venue_guidance import build_venue_guidance_text
from glorious_mess_reviewer.providers import LLMProvider, ProviderError
from glorious_mess_reviewer.schemas import ManuscriptInput, VenueProfile

T = TypeVar("T", bound=BaseModel)


class AgentCallError(RuntimeError):
    """Wrap a failed provider call while preserving the rendered prompt metadata."""

    def __init__(self, message: str, *, prompt: PromptTemplate) -> None:
        super().__init__(message)
        self.prompt = prompt


class BaseReviewAgent(ABC, Generic[T]):
    """Shared prompt-render-and-parse flow for a single subreviewer."""

    agent_name: str
    template_name: str
    response_model: type[T]

    def __init__(self, provider: LLMProvider | None, *, prompt_version: str = "v1") -> None:
        """Store the provider used by this panel worker."""

        self._provider = provider
        self._prompt_version = prompt_version

    def build_prompt(
        self,
        manuscript: ManuscriptInput,
        venue_profile: VenueProfile,
        **extra_context: Any,
    ) -> PromptTemplate:
        """Render the prompt template with agent-specific context."""

        # prompt 构造集中在这里，便于失败时也能记录版本和 hash。
        return render_prompt(
            self.template_name,
            version=self._prompt_version,
            manuscript=manuscript,
            venue_profile_json=json.dumps(venue_profile.model_dump(mode="json"), ensure_ascii=True, indent=2),
            venue_guidance_text=build_venue_guidance_text(venue_profile),
            venue_examples_text=build_venue_examples_text(self.template_name, venue_profile),
            **extra_context,
        )

    async def review(
        self,
        manuscript: ManuscriptInput,
        venue_profile: VenueProfile,
        **extra_context: Any,
    ) -> tuple[T, PromptTemplate]:
        """Render the agent prompt, call the provider, and return the typed output."""

        prompt = self.build_prompt(manuscript, venue_profile, **extra_context)
        if self._provider is None:
            raise AgentCallError(
                f"LLM provider unavailable for agent {self.agent_name}.",
                prompt=prompt,
            )
        try:
            response = await self._provider.complete_json(
                task_name=self.agent_name,
                prompt=prompt.content,
                response_model=self.response_model,
                metadata={
                    "manuscript_id": manuscript.manuscript_id,
                    "agent_name": self.agent_name,
                    "prompt_version": prompt.version,
                },
            )
        except ProviderError as exc:
            # 包装 provider 错误，避免上层在失败路径里丢掉 prompt 元数据。
            raise AgentCallError(str(exc), prompt=prompt) from exc
        return response, prompt
