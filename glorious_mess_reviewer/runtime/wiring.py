"""Shared runtime wiring for API and CLI entrypoints."""

from __future__ import annotations

import logging
from typing import Final

from glorious_mess_reviewer.config import Settings
from glorious_mess_reviewer.orchestrator import ReviewOrchestrator
from glorious_mess_reviewer.providers import LLMProvider, OpenAIChatCompletionsProvider, OpenAIResponsesProvider, ProviderError
from glorious_mess_reviewer.runtime.executor import WorkflowRuntime
from glorious_mess_reviewer.runtime.service import ReviewRuntimeService
from glorious_mess_reviewer.storage import SQLiteReviewStore
from glorious_mess_reviewer.workflows import (
    build_screening_review_workflow_spec,
    build_screening_risk_audit_workflow_spec,
    build_screening_venue_fit_audit_workflow_spec,
)

LOGGER = logging.getLogger(__name__)
_UNSET_PROVIDER: Final = object()


def build_store(settings: Settings) -> SQLiteReviewStore:
    """Create the SQLite store for the resolved runtime settings."""

    return SQLiteReviewStore(settings.database_path)


def build_provider(settings: Settings, *, log_degraded: bool = True) -> LLMProvider | None:
    """Resolve the configured LLM provider or return None for degraded mode."""

    if settings.provider_backend == "mock":
        if log_degraded:
            LOGGER.warning(
                "mock_backend_selected",
                extra={
                    "event": "mock_backend_selected",
                    "status": "degraded",
                    "details": {
                        "message": "Mock backend is test-only without injected fixture responses.",
                    },
                },
            )
        return None

    try:
        if settings.openai_api_style == "chat_completions":
            return OpenAIChatCompletionsProvider(settings)
        return OpenAIResponsesProvider(settings)
    except ProviderError as exc:
        if log_degraded:
            LOGGER.warning(
                "provider_unavailable_at_dependency_resolution",
                extra={
                    "event": "provider_unavailable_at_dependency_resolution",
                    "status": "degraded",
                    "details": {
                        "provider_backend": settings.provider_backend,
                        "reason": str(exc),
                    },
                },
            )
        return None


def build_orchestrator(
    settings: Settings,
    *,
    provider: LLMProvider | None | object = _UNSET_PROVIDER,
    store: SQLiteReviewStore | None = None,
) -> ReviewOrchestrator:
    """Build a review orchestrator with shared provider/store wiring rules."""

    resolved_store = store or build_store(settings)
    resolved_provider = build_provider(settings) if provider is _UNSET_PROVIDER else provider
    return ReviewOrchestrator(settings=settings, provider=resolved_provider, store=resolved_store)


def build_runtime(
    settings: Settings,
    *,
    provider: LLMProvider | None | object = _UNSET_PROVIDER,
    store: SQLiteReviewStore | None = None,
    orchestrator: ReviewOrchestrator | None = None,
) -> WorkflowRuntime:
    """Build the workflow runtime and register built-in workflows."""

    if orchestrator is not None:
        resolved_orchestrator = orchestrator
        resolved_store = resolved_orchestrator.store
        resolved_provider = resolved_orchestrator.provider
    else:
        resolved_store = store or build_store(settings)
        resolved_provider = build_provider(settings) if provider is _UNSET_PROVIDER else provider
        resolved_orchestrator = build_orchestrator(settings, provider=resolved_provider, store=resolved_store)

    runtime = WorkflowRuntime(settings=settings, provider=resolved_provider, store=resolved_store)
    runtime.register_workflow(build_screening_review_workflow_spec(orchestrator=resolved_orchestrator))
    runtime.register_workflow(build_screening_risk_audit_workflow_spec(orchestrator=resolved_orchestrator))
    runtime.register_workflow(build_screening_venue_fit_audit_workflow_spec(orchestrator=resolved_orchestrator))
    return runtime


def build_review_service(
    settings: Settings,
    *,
    provider: LLMProvider | None | object = _UNSET_PROVIDER,
    store: SQLiteReviewStore | None = None,
    orchestrator: ReviewOrchestrator | None = None,
) -> ReviewRuntimeService:
    """Build the application-facing review service with shared runtime wiring."""

    if orchestrator is not None:
        resolved_orchestrator = orchestrator
        resolved_store = resolved_orchestrator.store
        resolved_provider = resolved_orchestrator.provider
    else:
        resolved_store = store or build_store(settings)
        resolved_provider = build_provider(settings) if provider is _UNSET_PROVIDER else provider
        resolved_orchestrator = build_orchestrator(settings, provider=resolved_provider, store=resolved_store)

    runtime = build_runtime(settings, orchestrator=resolved_orchestrator)
    return ReviewRuntimeService(
        settings=settings,
        provider=resolved_provider,
        store=resolved_store,
        orchestrator=resolved_orchestrator,
        runtime=runtime,
    )
