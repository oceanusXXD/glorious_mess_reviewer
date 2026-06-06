"""SQLite persistence coverage for successful and degraded reviews."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest

from glorious_mess_reviewer.config import Settings
from glorious_mess_reviewer.orchestrator import ReviewOrchestrator
from glorious_mess_reviewer.providers import MockLLMProvider, ProviderError
from glorious_mess_reviewer.runtime import build_runtime
from glorious_mess_reviewer.schemas import ManuscriptInput, WorkflowSessionStatus
from glorious_mess_reviewer.storage import SQLiteReviewStore
from tests.conftest import load_fixture
from tests.mock_fixtures import build_mock_registry


def test_successful_review_persists_review_agent_and_event_rows(tmp_path: Path) -> None:
    settings = Settings(
        provider_backend="mock",
        database_path=tmp_path / "successful-review.db",
        minimum_reviewable_characters=200,
        store_raw_agent_outputs=True,
    )
    orchestrator = ReviewOrchestrator(
        settings=settings,
        provider=MockLLMProvider(build_mock_registry()),
        store=SQLiteReviewStore(settings.database_path),
    )

    result = asyncio.run(
        orchestrator.review(ManuscriptInput.model_validate(load_fixture("absurd_but_rigorous.json")))
    )

    assert result.final_recommendation.value == "ADVANCE_TO_FULL_REVIEW"
    with sqlite3.connect(settings.database_path) as connection:
        review_runs = connection.execute("SELECT COUNT(*) FROM review_runs").fetchone()
        agent_runs = connection.execute("SELECT COUNT(*) FROM agent_runs").fetchone()
        event_logs = connection.execute("SELECT COUNT(*) FROM event_logs").fetchone()

    assert review_runs == (1,)
    assert agent_runs == (4,)
    assert event_logs is not None and event_logs[0] >= 6


def test_successful_review_persists_expected_json_payloads(tmp_path: Path) -> None:
    settings = Settings(
        provider_backend="mock",
        database_path=tmp_path / "successful-review-content.db",
        minimum_reviewable_characters=200,
        store_raw_agent_outputs=True,
    )
    orchestrator = ReviewOrchestrator(
        settings=settings,
        provider=MockLLMProvider(build_mock_registry()),
        store=SQLiteReviewStore(settings.database_path),
    )

    result = asyncio.run(
        orchestrator.review(ManuscriptInput.model_validate(load_fixture("absurd_but_rigorous.json")))
    )

    with sqlite3.connect(settings.database_path) as connection:
        request_payload_json, review_json = connection.execute(
            "SELECT request_payload_json, review_json FROM review_runs"
        ).fetchone()
        agent_rows = connection.execute(
            "SELECT agent_name, status, payload_json FROM agent_runs ORDER BY id"
        ).fetchall()
        event_rows = connection.execute(
            "SELECT event_type, payload_json FROM event_logs ORDER BY id"
        ).fetchall()

    request_payload = json.loads(request_payload_json)
    persisted_review = json.loads(review_json)
    review_requested_payload = json.loads(event_rows[0][1])
    recommendation_payload = json.loads(event_rows[-1][1])

    assert request_payload["manuscript_id"] == "absurd-rigorous-001"
    assert request_payload["venue_profile"] is None
    assert persisted_review["workflow_session_id"]
    assert persisted_review["final_recommendation"] == result.final_recommendation.value
    assert persisted_review["resolved_venue_profile"]["venue_name"] == "S.H.I.T Initial Screening Desk"
    assert persisted_review["resolved_venue_profile"]["preset_name"] == "shit-screening-default"
    assert persisted_review["resolved_venue_profile"]["minimum_reviewable_characters"] == 200
    assert persisted_review["raw_agent_outputs"]["FinalSedimentCouncil"]["status"] == "success"
    assert persisted_review["raw_agent_outputs"]["FinalSedimentCouncil"]["artifact_type"] == "meta_output"
    assert [row[0] for row in agent_rows] == [
        "HanCeGateAgent",
        "EvidenceSludgeEngine",
        "AbsurdityButMakeItRigorous",
        "FinalSedimentCouncil",
    ]
    assert all(row[1] == "success" for row in agent_rows)
    assert json.loads(agent_rows[0][2])["decision"] == "pass"
    assert event_rows[0][0] == "review_requested"
    assert event_rows[-1][0] == "recommendation_generated"
    assert review_requested_payload["provider_backend"] == "mock"
    assert review_requested_payload["resolved_venue_profile"]["preset_name"] == "shit-screening-default"
    assert review_requested_payload["resolved_venue_profile"]["minimum_reviewable_characters"] == 200
    assert recommendation_payload["recommendation"] == "ADVANCE_TO_FULL_REVIEW"
    assert recommendation_payload["final_score"] == 4.76


def test_missing_provider_for_review_does_not_persist_partial_rows(tmp_path: Path) -> None:
    settings = Settings(
        provider_backend="openai",
        openai_api_key=None,
        database_path=tmp_path / "missing-provider-blocked.db",
        minimum_reviewable_characters=20,
    )
    orchestrator = ReviewOrchestrator(
        settings=settings,
        provider=None,
        store=SQLiteReviewStore(settings.database_path),
    )
    manuscript = ManuscriptInput.model_validate(load_fixture("funny_but_hollow.json") | {"abstract": ""})

    with pytest.raises(ProviderError):
        asyncio.run(orchestrator.review(manuscript))

    with sqlite3.connect(settings.database_path) as connection:
        review_runs = connection.execute("SELECT COUNT(*) FROM review_runs").fetchone()
        agent_runs = connection.execute("SELECT COUNT(*) FROM agent_runs").fetchone()
        retry_records = connection.execute("SELECT COUNT(*) FROM retry_records").fetchone()
        event_logs = connection.execute("SELECT COUNT(*) FROM event_logs").fetchone()

    assert review_runs == (0,)
    assert agent_runs == (0,)
    assert retry_records == (0,)
    assert event_logs == (0,)


def test_store_transaction_commits_grouped_writes(tmp_path: Path) -> None:
    database_path = tmp_path / "transaction-commit.db"
    store = SQLiteReviewStore(database_path)

    with store.transaction():
        store.save_event(
            run_id="run-1",
            event_type="review_requested",
            level="INFO",
            created_at="2026-04-09T00:00:00+00:00",
            payload={"manuscript_id": "m1"},
        )
        store.save_retry_record(
            run_id="run-1",
            stage="HanCeGateAgent",
            reason="transient",
            created_at="2026-04-09T00:00:01+00:00",
        )

    with sqlite3.connect(database_path) as connection:
        event_count = connection.execute("SELECT COUNT(*) FROM event_logs").fetchone()
        retry_count = connection.execute("SELECT COUNT(*) FROM retry_records").fetchone()

    assert event_count == (1,)
    assert retry_count == (1,)


def test_store_transaction_rolls_back_grouped_writes_on_error(tmp_path: Path) -> None:
    database_path = tmp_path / "transaction-rollback.db"
    store = SQLiteReviewStore(database_path)

    with pytest.raises(RuntimeError, match="boom"):
        with store.transaction():
            store.save_event(
                run_id="run-2",
                event_type="review_requested",
                level="INFO",
                created_at="2026-04-09T00:00:00+00:00",
                payload={"manuscript_id": "m2"},
            )
            raise RuntimeError("boom")

    with sqlite3.connect(database_path) as connection:
        event_count = connection.execute("SELECT COUNT(*) FROM event_logs").fetchone()

    assert event_count == (0,)


def test_store_can_load_persisted_review_by_run_id(tmp_path: Path) -> None:
    settings = Settings(
        provider_backend="mock",
        database_path=tmp_path / "review-query.db",
        minimum_reviewable_characters=200,
        store_raw_agent_outputs=True,
    )
    store = SQLiteReviewStore(settings.database_path)
    orchestrator = ReviewOrchestrator(
        settings=settings,
        provider=MockLLMProvider(build_mock_registry()),
        store=store,
    )

    review = asyncio.run(
        orchestrator.review(ManuscriptInput.model_validate(load_fixture("absurd_but_rigorous.json")))
    )

    with sqlite3.connect(settings.database_path) as connection:
        run_id = connection.execute("SELECT run_id FROM review_runs ORDER BY created_at DESC LIMIT 1").fetchone()[0]

    persisted = store.get_review(run_id)

    assert persisted is not None
    assert persisted.run_id == run_id
    assert persisted.review.manuscript_id == review.manuscript_id
    assert persisted.review.final_recommendation == review.final_recommendation
    assert persisted.request_payload.manuscript_id == review.manuscript_id


def test_store_can_list_review_summaries_with_filter_and_limit(tmp_path: Path) -> None:
    settings = Settings(
        provider_backend="mock",
        database_path=tmp_path / "review-list.db",
        minimum_reviewable_characters=200,
        store_raw_agent_outputs=True,
    )
    store = SQLiteReviewStore(settings.database_path)
    orchestrator = ReviewOrchestrator(
        settings=settings,
        provider=MockLLMProvider(build_mock_registry()),
        store=store,
    )

    asyncio.run(orchestrator.review(ManuscriptInput.model_validate(load_fixture("absurd_but_rigorous.json"))))
    asyncio.run(orchestrator.review(ManuscriptInput.model_validate(load_fixture("funny_but_hollow.json"))))

    summaries = store.list_reviews(limit=1)
    filtered = store.list_reviews(manuscript_id="absurd-rigorous-001", limit=5)

    assert len(summaries) == 1
    assert summaries[0].run_id
    assert summaries[0].manuscript_id == "funny-hollow-002"
    assert summaries[0].final_recommendation == "REJECT_AS_EMPTY_GIMMICK"
    assert summaries[0].resolved_venue_profile.preset_name == "shit-screening-default"
    assert len(filtered) == 1
    assert filtered[0].manuscript_id == "absurd-rigorous-001"


def test_store_backfills_resolved_venue_profile_for_legacy_rows(tmp_path: Path) -> None:
    store = SQLiteReviewStore(tmp_path / "legacy-query.db")
    legacy_request = ManuscriptInput.model_validate(load_fixture("absurd_but_rigorous.json"))
    settings = Settings(
        provider_backend="mock",
        database_path=tmp_path / "legacy-query.db",
        minimum_reviewable_characters=200,
        store_raw_agent_outputs=True,
    )
    orchestrator = ReviewOrchestrator(
        settings=settings,
        provider=MockLLMProvider(build_mock_registry()),
        store=store,
    )
    review = asyncio.run(orchestrator.review(legacy_request))

    with sqlite3.connect(settings.database_path) as connection:
        run_id, review_json = connection.execute(
            "SELECT run_id, review_json FROM review_runs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        legacy_payload = json.loads(review_json)
        legacy_payload.pop("resolved_venue_profile", None)
        connection.execute(
            "UPDATE review_runs SET review_json = ? WHERE run_id = ?",
            (json.dumps(legacy_payload, ensure_ascii=True), run_id),
        )
        connection.commit()

    restored = store.get_review(run_id)
    summaries = store.list_reviews(limit=5)

    assert restored is not None
    assert restored.review.resolved_venue_profile.preset_name == "shit-screening-default"
    assert restored.review.resolved_venue_profile.minimum_reviewable_characters == 200
    assert summaries[0].resolved_venue_profile.preset_name == "shit-screening-default"


def test_partial_failure_review_persists_retry_records(tmp_path: Path) -> None:
    registry = build_mock_registry()
    registry.pop(("partial-failure-004", "AbsurdityButMakeItRigorous"), None)
    registry.pop(("partial-failure-004", "FinalSedimentCouncil"), None)

    settings = Settings(
        provider_backend="mock",
        database_path=tmp_path / "partial-failure.db",
        minimum_reviewable_characters=200,
        store_raw_agent_outputs=True,
    )
    orchestrator = ReviewOrchestrator(
        settings=settings,
        provider=MockLLMProvider(registry),
        store=SQLiteReviewStore(settings.database_path),
    )

    result = asyncio.run(
        orchestrator.review(ManuscriptInput.model_validate(load_fixture("partial_failure.json")))
    )

    assert result.agent_failures
    with sqlite3.connect(settings.database_path) as connection:
        review_runs = connection.execute("SELECT COUNT(*) FROM review_runs").fetchone()
        retry_records = connection.execute("SELECT COUNT(*) FROM retry_records").fetchone()
        failed_agents = connection.execute(
            "SELECT COUNT(*) FROM agent_runs WHERE status = ?",
            ("failed",),
        ).fetchone()

    assert review_runs == (1,)
    assert retry_records is not None and retry_records[0] >= 2
    assert failed_agents is not None and failed_agents[0] >= 2


def test_precheck_agent_fallback_persists_retry_and_event_content(tmp_path: Path) -> None:
    registry = build_mock_registry()
    registry.pop(("absurd-rigorous-001", "HanCeGateAgent"), None)

    settings = Settings(
        provider_backend="mock",
        database_path=tmp_path / "precheck-fallback.db",
        minimum_reviewable_characters=200,
        store_raw_agent_outputs=True,
    )
    orchestrator = ReviewOrchestrator(
        settings=settings,
        provider=MockLLMProvider(registry),
        store=SQLiteReviewStore(settings.database_path),
    )

    result = asyncio.run(
        orchestrator.review(ManuscriptInput.model_validate(load_fixture("absurd_but_rigorous.json")))
    )

    with sqlite3.connect(settings.database_path) as connection:
        retry_rows = connection.execute(
            "SELECT stage, reason FROM retry_records ORDER BY id"
        ).fetchall()
        failed_agent_row = connection.execute(
            "SELECT status, error_message FROM agent_runs WHERE agent_name = ? ORDER BY id DESC LIMIT 1",
            ("HanCeGateAgent",),
        ).fetchone()
        event_rows = connection.execute(
            "SELECT event_type, payload_json FROM event_logs ORDER BY id"
        ).fetchall()
        persisted_review_json = connection.execute("SELECT review_json FROM review_runs").fetchone()[0]

    persisted_review = json.loads(persisted_review_json)
    agent_failed_payload = json.loads(next(payload for event_type, payload in event_rows if event_type == "agent_failed"))

    assert result.final_recommendation.value == "ADVANCE_TO_FULL_REVIEW"
    assert persisted_review["raw_agent_outputs"]["HanCeGateAgent"]["status"] == "fallback"
    assert persisted_review["raw_agent_outputs"]["HanCeGateAgent"]["artifact_type"] == "precheck_output"
    assert persisted_review["agent_failures"][0]["agent_name"] == "HanCeGateAgent"
    assert retry_rows == [
        (
            "HanCeGateAgent",
            "mock registry missing response for ('absurd-rigorous-001', 'HanCeGateAgent')",
        )
    ]
    assert failed_agent_row == (
        "failed",
        "mock registry missing response for ('absurd-rigorous-001', 'HanCeGateAgent')",
    )
    assert agent_failed_payload == {
        "agent_name": "HanCeGateAgent",
        "message": "mock registry missing response for ('absurd-rigorous-001', 'HanCeGateAgent')",
    }


def test_successful_review_persists_runtime_session_tables(tmp_path: Path) -> None:
    settings = Settings(
        provider_backend="mock",
        database_path=tmp_path / "runtime-session-persistence.db",
        minimum_reviewable_characters=200,
        store_raw_agent_outputs=True,
    )
    runtime = build_runtime(
        settings,
        provider=MockLLMProvider(build_mock_registry()),
        store=SQLiteReviewStore(settings.database_path),
    )

    session = asyncio.run(
        runtime.run_workflow(
            "screening.review.v1",
            ManuscriptInput.model_validate(load_fixture("absurd_but_rigorous.json")),
        )
    )

    with sqlite3.connect(settings.database_path) as connection:
        workflow_session_row = connection.execute(
            "SELECT workflow_id, manuscript_id, status FROM workflow_sessions WHERE session_id = ?",
            (session.session_id,),
        ).fetchone()
        step_count = connection.execute(
            "SELECT COUNT(*) FROM workflow_steps WHERE session_id = ?",
            (session.session_id,),
        ).fetchone()
        artifact_keys = {
            row[0]
            for row in connection.execute(
                "SELECT artifact_key FROM workflow_artifacts WHERE session_id = ?",
                (session.session_id,),
            ).fetchall()
        }

    assert workflow_session_row == ("screening.review.v1", "absurd-rigorous-001", "completed")
    assert step_count is not None and step_count[0] >= 7
    assert {"venue.resolved", "precheck.local", "precheck.effective", "decision.review_output"} <= artifact_keys


def test_store_can_list_workflow_session_summaries_with_filters(tmp_path: Path) -> None:
    settings = Settings(
        provider_backend="mock",
        database_path=tmp_path / "workflow-session-summaries.db",
        minimum_reviewable_characters=200,
        store_raw_agent_outputs=True,
    )
    store = SQLiteReviewStore(settings.database_path)
    runtime = build_runtime(
        settings,
        provider=MockLLMProvider(build_mock_registry()),
        store=store,
    )

    asyncio.run(
        runtime.run_workflow(
            "screening.risk_audit.v1",
            ManuscriptInput.model_validate(load_fixture("absurd_but_rigorous.json")),
        )
    )
    asyncio.run(
        runtime.run_workflow(
            "screening.venue_fit_audit.v1",
            ManuscriptInput.model_validate(load_fixture("funny_but_hollow.json")),
        )
    )

    all_summaries = store.list_workflow_sessions(limit=10)
    filtered = store.list_workflow_sessions(
        workflow_id="screening.risk_audit.v1",
        manuscript_id="absurd-rigorous-001",
        status=WorkflowSessionStatus.completed,
        limit=10,
    )

    assert len(all_summaries) == 2
    assert len(filtered) == 1
    assert filtered[0].workflow_id == "screening.risk_audit.v1"
    assert filtered[0].manuscript_id == "absurd-rigorous-001"
    assert filtered[0].status == WorkflowSessionStatus.completed
    assert filtered[0].final_output_type == "risk_audit_output"


def test_store_initializes_schema_metadata_and_query_indexes(tmp_path: Path) -> None:
    database_path = tmp_path / "schema-metadata.db"
    SQLiteReviewStore(database_path)

    with sqlite3.connect(database_path) as connection:
        schema_version = connection.execute(
            "SELECT value FROM schema_metadata WHERE key = ?",
            ("schema_version",),
        ).fetchone()
        index_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            ).fetchall()
        }

    assert schema_version == ("2",)
    assert {
        "idx_review_runs_manuscript_created",
        "idx_event_logs_run_type",
        "idx_workflow_sessions_browse",
    } <= index_names


def test_store_migrates_legacy_workflow_sessions_with_indexed_manuscript_id(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy-workflow-session.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE workflow_sessions (
                session_id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                request_payload_json TEXT NOT NULL,
                final_output_json TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO workflow_sessions (
                session_id,
                workflow_id,
                status,
                created_at,
                updated_at,
                request_payload_json,
                final_output_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-session-1",
                "screening.risk_audit.v1",
                "completed",
                "2026-04-09T00:00:00+00:00",
                "2026-04-09T00:00:01+00:00",
                json.dumps({"manuscript_id": "legacy-001"}),
                None,
            ),
        )

    store = SQLiteReviewStore(database_path)
    summaries = store.list_workflow_sessions(manuscript_id="legacy-001", limit=10)

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT manuscript_id FROM workflow_sessions WHERE session_id = ?",
            ("legacy-session-1",),
        ).fetchone()

    assert row == ("legacy-001",)
    assert len(summaries) == 1
    assert summaries[0].session_id == "legacy-session-1"
