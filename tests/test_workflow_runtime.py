"""Workflow runtime persistence and artifact coverage."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sqlite3

import pytest

from glorious_mess_reviewer.config import Settings
from glorious_mess_reviewer.providers import MockLLMProvider, ProviderError
from glorious_mess_reviewer.runtime import WorkflowExecutionResult, WorkflowRuntime, WorkflowSpec, build_runtime
from glorious_mess_reviewer.schemas import ManuscriptInput, WorkflowSessionStatus
from glorious_mess_reviewer.storage import SQLiteReviewStore
from tests.conftest import load_fixture
from tests.mock_fixtures import build_mock_registry


def test_runtime_persists_workflow_session_steps_and_artifacts(tmp_path: Path) -> None:
    settings = Settings(
        provider_backend="mock",
        database_path=tmp_path / "workflow-runtime.db",
        minimum_reviewable_characters=200,
        store_raw_agent_outputs=True,
    )
    store = SQLiteReviewStore(settings.database_path)
    runtime = build_runtime(
        settings,
        provider=MockLLMProvider(build_mock_registry()),
        store=store,
    )

    session = asyncio.run(
        runtime.run_workflow(
            "screening.review.v1",
            ManuscriptInput.model_validate(load_fixture("absurd_but_rigorous.json")),
        )
    )
    persisted = store.get_workflow_session(session.session_id)

    assert persisted is not None
    assert persisted.workflow_id == "screening.review.v1"
    assert persisted.status == WorkflowSessionStatus.completed
    assert persisted.final_output is not None
    assert persisted.final_output["workflow_session_id"] == session.session_id
    assert persisted.final_output["final_recommendation"] == "ADVANCE_TO_FULL_REVIEW"
    assert {artifact.artifact_key for artifact in persisted.artifacts} >= {
        "venue.resolved",
        "precheck.local",
        "precheck.llm",
        "precheck.effective",
        "panel.evidence",
        "panel.value",
        "panel.meta",
        "decision.rule_hits",
        "decision.review_output",
    }
    assert {step.node_id for step in persisted.steps} >= {
        "resolve_venue",
        "precheck.local",
        "precheck.llm",
        "panel.evidence",
        "panel.value",
        "panel.meta",
        "projection.review",
    }
    artifact_map = {artifact.artifact_key: artifact.payload for artifact in persisted.artifacts}
    assert artifact_map["venue.resolved"].artifact_type.value == "venue_profile"
    assert artifact_map["precheck.llm"].artifact_type.value == "agent_output"
    assert artifact_map["decision.review_output"].artifact_type.value == "review_output"


def test_runtime_marks_downstream_steps_skipped_when_precheck_blocks_review(tmp_path: Path) -> None:
    settings = Settings(
        provider_backend="mock",
        database_path=tmp_path / "workflow-blocked.db",
        minimum_reviewable_characters=200,
        store_raw_agent_outputs=True,
    )
    store = SQLiteReviewStore(settings.database_path)
    runtime = build_runtime(
        settings,
        provider=MockLLMProvider(build_mock_registry()),
        store=store,
    )

    blocked_payload = load_fixture("funny_but_hollow.json")
    blocked_payload["abstract"] = ""
    session = asyncio.run(
        runtime.run_workflow(
            "screening.review.v1",
            ManuscriptInput.model_validate(blocked_payload),
        )
    )

    persisted = store.get_workflow_session(session.session_id)

    assert persisted is not None
    step_statuses = {step.node_id: step.status.value for step in persisted.steps}
    assert step_statuses["panel.evidence"] == "skipped"
    assert step_statuses["panel.value"] == "skipped"
    assert step_statuses["panel.meta"] == "skipped"
    assert persisted.final_output is not None
    assert persisted.final_output["workflow_session_id"] == session.session_id
    assert persisted.final_output["final_recommendation"] == "REVISION_REQUIRED_BEFORE_REVIEW"


def test_runtime_can_execute_risk_audit_workflow(tmp_path: Path) -> None:
    settings = Settings(
        provider_backend="mock",
        database_path=tmp_path / "workflow-risk-audit.db",
        minimum_reviewable_characters=200,
        store_raw_agent_outputs=True,
    )
    store = SQLiteReviewStore(settings.database_path)
    runtime = build_runtime(
        settings,
        provider=MockLLMProvider(build_mock_registry()),
        store=store,
    )

    payload = load_fixture("absurd_but_rigorous.json")
    payload["abstract"] = "This draft teaches readers how to weaponize office chairs."
    session = asyncio.run(
        runtime.run_workflow(
            "screening.risk_audit.v1",
            ManuscriptInput.model_validate(payload),
        )
    )
    persisted = store.get_workflow_session(session.session_id)

    assert persisted is not None
    assert persisted.workflow_id == "screening.risk_audit.v1"
    assert persisted.status == WorkflowSessionStatus.completed
    assert persisted.final_output is not None
    assert persisted.final_output["workflow_session_id"] == session.session_id
    assert persisted.final_output["action"] == "FLAG_FOR_HUMAN_REVIEW"
    assert {step.node_id for step in persisted.steps} == {
        "resolve_venue",
        "precheck.local",
        "precheck.llm",
        "projection.risk_audit",
    }
    artifact_map = {artifact.artifact_key: artifact.payload for artifact in persisted.artifacts}
    assert artifact_map["decision.risk_audit_output"].artifact_type.value == "risk_audit_output"


def test_runtime_can_execute_venue_fit_audit_workflow(tmp_path: Path) -> None:
    settings = Settings(
        provider_backend="mock",
        database_path=tmp_path / "workflow-venue-fit.db",
        minimum_reviewable_characters=200,
        store_raw_agent_outputs=True,
    )
    store = SQLiteReviewStore(settings.database_path)
    runtime = build_runtime(
        settings,
        provider=MockLLMProvider(build_mock_registry()),
        store=store,
    )

    session = asyncio.run(
        runtime.run_workflow(
            "screening.venue_fit_audit.v1",
            ManuscriptInput.model_validate(load_fixture("absurd_but_rigorous.json")),
        )
    )
    persisted = store.get_workflow_session(session.session_id)

    assert persisted is not None
    assert persisted.workflow_id == "screening.venue_fit_audit.v1"
    assert persisted.status == WorkflowSessionStatus.completed
    assert persisted.final_output is not None
    assert persisted.final_output["workflow_session_id"] == session.session_id
    assert persisted.final_output["action"] == "STRONG_FIT"
    assert {step.node_id for step in persisted.steps} == {
        "resolve_venue",
        "precheck.local",
        "precheck.llm",
        "panel.value",
        "projection.venue_fit_audit",
    }
    artifact_map = {artifact.artifact_key: artifact.payload for artifact in persisted.artifacts}
    assert artifact_map["decision.venue_fit_audit_output"].artifact_type.value == "venue_fit_audit_output"


def test_runtime_persists_failure_event_for_failed_workflow(tmp_path: Path) -> None:
    settings = Settings(
        provider_backend="openai",
        openai_api_key=None,
        database_path=tmp_path / "workflow-failed.db",
        minimum_reviewable_characters=200,
    )
    store = SQLiteReviewStore(settings.database_path)
    runtime = build_runtime(settings, provider=None, store=store)

    with pytest.raises(ProviderError):
        asyncio.run(
            runtime.run_workflow(
                "screening.review.v1",
                ManuscriptInput.model_validate(load_fixture("absurd_but_rigorous.json")),
            )
        )

    summaries = store.list_workflow_sessions(status=WorkflowSessionStatus.failed, limit=10)
    assert len(summaries) == 1
    assert summaries[0].workflow_id == "screening.review.v1"
    assert summaries[0].manuscript_id == "absurd-rigorous-001"
    with sqlite3.connect(settings.database_path) as connection:
        row = connection.execute(
            "SELECT payload_json FROM event_logs WHERE event_type = ? ORDER BY id DESC LIMIT 1",
            ("workflow_failed",),
        ).fetchone()

    assert row is not None
    payload = json.loads(row[0])
    assert payload["session_id"] == summaries[0].session_id
    assert payload["workflow_id"] == "screening.review.v1"
    assert payload["exception_type"] == "ProviderError"
    assert "requires a configured LLM provider" in payload["message"]


def test_runtime_marks_session_failed_when_completion_persistence_fails(tmp_path: Path) -> None:
    settings = Settings(
        provider_backend="mock",
        database_path=tmp_path / "workflow-persistence-failed.db",
    )
    store = SQLiteReviewStore(settings.database_path)
    runtime = WorkflowRuntime(settings=settings, provider=None, store=store)

    async def invalid_final_output_workflow(_context):
        return WorkflowExecutionResult(final_output={"not_json": {1, 2}}, steps=[], artifacts={})

    runtime.register_workflow(
        WorkflowSpec(
            workflow_id="test.persistence_failure.v1",
            description="Workflow that returns a non-JSON final output for failure-path coverage.",
            runner=invalid_final_output_workflow,
        )
    )

    with pytest.raises(TypeError):
        asyncio.run(
            runtime.run_workflow(
                "test.persistence_failure.v1",
                ManuscriptInput.model_validate(load_fixture("absurd_but_rigorous.json")),
            )
        )

    summaries = store.list_workflow_sessions(status=WorkflowSessionStatus.failed, limit=10)
    assert len(summaries) == 1
    assert summaries[0].workflow_id == "test.persistence_failure.v1"
    with sqlite3.connect(settings.database_path) as connection:
        row = connection.execute(
            "SELECT payload_json FROM event_logs WHERE event_type = ? ORDER BY id DESC LIMIT 1",
            ("workflow_failed",),
        ).fetchone()

    assert row is not None
    payload = json.loads(row[0])
    assert payload["exception_type"] == "TypeError"
    assert "not JSON serializable" in payload["message"]
