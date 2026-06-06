"""Runtime wiring tests for provider/store/orchestrator creation."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from glorious_mess_reviewer.config import Settings
from glorious_mess_reviewer.providers import MockLLMProvider, OpenAIResponsesProvider
from glorious_mess_reviewer.runtime import (
    WorkflowRuntime,
    build_orchestrator,
    build_provider,
    build_runtime,
    build_store,
)
from glorious_mess_reviewer.schemas import ManuscriptInput, WorkflowSessionStatus
from glorious_mess_reviewer.storage import SQLiteReviewStore
from tests.conftest import load_fixture
from tests.mock_fixtures import build_mock_registry


def test_build_provider_returns_none_for_mock_backend(tmp_path: Path) -> None:
    settings = Settings(provider_backend="mock", database_path=tmp_path / "runtime-mock.db")

    provider = build_provider(settings, log_degraded=False)

    assert provider is None


def test_build_provider_creates_openai_provider_when_key_present(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeAsyncOpenAI:
        def __init__(self, **kwargs: object) -> None:
            self.api_key = kwargs.get("api_key")
            self.base_url = kwargs.get("base_url")
            self.timeout = kwargs.get("timeout")
            self.max_retries = kwargs.get("max_retries")
            self.responses = SimpleNamespace(parse=None)

    monkeypatch.setattr("glorious_mess_reviewer.providers.openai_provider.AsyncOpenAI", _FakeAsyncOpenAI)

    settings = Settings(
        provider_backend="openai",
        openai_api_key="test-key",
        database_path=tmp_path / "runtime-openai.db",
    )

    provider = build_provider(settings, log_degraded=False)

    assert isinstance(provider, OpenAIResponsesProvider)


def test_build_orchestrator_preserves_explicit_provider_and_store(tmp_path: Path) -> None:
    settings = Settings(provider_backend="mock", database_path=tmp_path / "runtime-store.db")
    store = build_store(settings)

    orchestrator = build_orchestrator(settings, provider=None, store=store)

    assert isinstance(store, SQLiteReviewStore)
    assert orchestrator._provider is None
    assert orchestrator._store is store


def test_build_runtime_registers_screening_review_workflow(tmp_path: Path) -> None:
    settings = Settings(
        provider_backend="mock",
        database_path=tmp_path / "runtime-registry.db",
        minimum_reviewable_characters=200,
        store_raw_agent_outputs=True,
    )
    runtime = build_runtime(
        settings,
        provider=MockLLMProvider(build_mock_registry()),
        store=build_store(settings),
    )

    assert isinstance(runtime, WorkflowRuntime)
    assert "screening.review.v1" in runtime.list_workflows()
    assert "screening.risk_audit.v1" in runtime.list_workflows()
    assert "screening.venue_fit_audit.v1" in runtime.list_workflows()


def test_runtime_can_execute_screening_review_workflow(tmp_path: Path) -> None:
    settings = Settings(
        provider_backend="mock",
        database_path=tmp_path / "runtime-screening.db",
        minimum_reviewable_characters=200,
        store_raw_agent_outputs=True,
    )
    runtime = build_runtime(
        settings,
        provider=MockLLMProvider(build_mock_registry()),
        store=build_store(settings),
    )

    session = asyncio.run(
        runtime.run_workflow(
            "screening.review.v1",
            ManuscriptInput.model_validate(load_fixture("absurd_but_rigorous.json")),
        )
    )

    assert session.workflow_id == "screening.review.v1"
    assert session.status == WorkflowSessionStatus.completed
    assert session.final_output is not None
    assert session.final_output["final_recommendation"] == "ADVANCE_TO_FULL_REVIEW"
    assert {step.node_id for step in session.steps} >= {
        "resolve_venue",
        "precheck.local",
        "precheck.llm",
        "panel.evidence",
        "panel.value",
        "panel.meta",
        "projection.review",
    }


def test_runtime_exposes_workflow_spec_metadata(tmp_path: Path) -> None:
    settings = Settings(
        provider_backend="mock",
        database_path=tmp_path / "runtime-spec.db",
        minimum_reviewable_characters=200,
        store_raw_agent_outputs=True,
    )
    runtime = build_runtime(
        settings,
        provider=MockLLMProvider(build_mock_registry()),
        store=build_store(settings),
    )

    specs = runtime.list_workflow_specs()

    assert len(specs) == 3
    assert specs[0].workflow_id == "screening.review.v1"
    assert specs[0].node_ids == (
        "resolve_venue",
        "precheck.local",
        "precheck.llm",
        "panel.evidence",
        "panel.value",
        "panel.meta",
        "projection.review",
    )
    assert "screening" in specs[0].tags
    assert specs[1].workflow_id == "screening.risk_audit.v1"
    assert specs[1].node_ids == (
        "resolve_venue",
        "precheck.local",
        "precheck.llm",
        "projection.risk_audit",
    )
    assert "risk-audit" in specs[1].tags
    assert specs[2].workflow_id == "screening.venue_fit_audit.v1"
    assert specs[2].node_ids == (
        "resolve_venue",
        "precheck.local",
        "precheck.llm",
        "panel.value",
        "projection.venue_fit_audit",
    )
    assert "venue-fit" in specs[2].tags
