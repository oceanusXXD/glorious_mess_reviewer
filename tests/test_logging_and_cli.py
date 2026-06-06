"""Prompt logging and CLI behavior tests."""

from __future__ import annotations

import contextlib
import io
import sqlite3
from pathlib import Path
import json
import runpy
import sys
import asyncio

import pytest

from glorious_mess_reviewer.cli.main import build_parser, run_cli
from glorious_mess_reviewer.config import Settings
from glorious_mess_reviewer.orchestrator import ReviewOrchestrator
from glorious_mess_reviewer.runtime import build_runtime
from glorious_mess_reviewer.schemas import ManuscriptInput
from glorious_mess_reviewer.providers import MockLLMProvider
from glorious_mess_reviewer.storage import SQLiteReviewStore
from tests.conftest import load_fixture
from tests.mock_fixtures import build_mock_registry


def test_cli_parser_exposes_serve_and_show_default_venue() -> None:
    parser = build_parser()
    help_text = parser.format_help()
    subparser_action = next(action for action in parser._actions if getattr(action, "choices", None))
    review_help = subparser_action.choices["review"].format_help()
    risk_audit_help = subparser_action.choices["risk-audit"].format_help()
    venue_fit_audit_help = subparser_action.choices["venue-fit-audit"].format_help()
    show_venue_help = subparser_action.choices["show-default-venue"].format_help()
    show_review_help = subparser_action.choices["show-review"].format_help()
    show_review_display_help = subparser_action.choices["show-review-display"].format_help()
    show_workflow_help = subparser_action.choices["show-workflow"].format_help()
    list_reviews_help = subparser_action.choices["list-reviews"].format_help()
    list_review_displays_help = subparser_action.choices["list-review-displays"].format_help()
    review_display_overview_help = subparser_action.choices["review-display-overview"].format_help()
    list_workflows_help = subparser_action.choices["list-workflows"].format_help()
    list_workflow_sessions_help = subparser_action.choices["list-workflow-sessions"].format_help()
    doctor_help = subparser_action.choices["doctor"].format_help()
    new_manuscript_help = subparser_action.choices["new-manuscript"].format_help()
    benchmark_help = subparser_action.choices["benchmark"].format_help()
    assert "show-default-venue" in help_text
    assert "serve" in help_text
    assert "show-review" in help_text
    assert "show-review-display" in help_text
    assert "show-workflow" in help_text
    assert "list-reviews" in help_text
    assert "list-review-displays" in help_text
    assert "review-display-overview" in help_text
    assert "list-workflows" in help_text
    assert "list-workflow-sessions" in help_text
    assert "doctor" in help_text
    assert "new-manuscript" in help_text
    assert "benchmark" in help_text
    assert "venue-fit-audit" in help_text
    assert "--preset" in review_help
    assert "--report-output" in review_help
    assert "--preset" in risk_audit_help
    assert "--preset" in venue_fit_audit_help
    assert "--preset" in show_venue_help
    assert "--run-id" in show_review_help
    assert "--run-id" in show_review_display_help
    assert "--session-id" in show_workflow_help
    assert "--limit" in list_reviews_help
    assert "--limit" in list_review_displays_help
    assert "--manuscript-id" in list_review_displays_help
    assert "--lane" in list_review_displays_help
    assert "--sort" in list_review_displays_help
    assert "--limit" in review_display_overview_help
    assert "--manuscript-id" in review_display_overview_help
    assert "List registered workflow metadata" in list_workflows_help
    assert "--workflow-id" in list_workflow_sessions_help
    assert "--status" in list_workflow_sessions_help
    assert "--require-provider" in doctor_help
    assert "--manuscript-id" in new_manuscript_help
    assert "--markdown-output" in benchmark_help


def test_failed_agent_log_still_records_prompt_version(tmp_path: Path) -> None:
    registry = build_mock_registry()
    registry.pop(("partial-failure-004", "AbsurdityButMakeItRigorous"), None)
    settings = Settings(
        provider_backend="mock",
        database_path=tmp_path / "prompt-log.db",
        minimum_reviewable_characters=200,
        prompt_version="audit-v2",
    )
    orchestrator = ReviewOrchestrator(
        settings=settings,
        provider=MockLLMProvider(registry),
        store=SQLiteReviewStore(settings.database_path),
    )
    from glorious_mess_reviewer.schemas import ManuscriptInput
    from tests.conftest import load_fixture

    result = __import__("asyncio").run(orchestrator.review(ManuscriptInput.model_validate(load_fixture("partial_failure.json"))))
    assert result.agent_failures

    with sqlite3.connect(settings.database_path) as connection:
        row = connection.execute(
            "SELECT prompt_version, prompt_hash FROM agent_runs WHERE agent_name = ? AND status = ? ORDER BY id DESC LIMIT 1",
            ("AbsurdityButMakeItRigorous", "failed"),
        ).fetchone()

    assert row is not None
    assert row[0] == "audit-v2"
    assert row[1] != "unknown"


def _fixture_path(name: str) -> Path:
    return Path(__file__).resolve().parent / "fixtures" / name


def _run_cli(*args: str, settings: Settings | None = None) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = run_cli(list(args), settings=settings, stdout=stdout, stderr=stderr)
    return exit_code, stdout.getvalue(), stderr.getvalue()


def test_cli_dry_run_persists_sqlite_event(tmp_path: Path) -> None:
    database_path = tmp_path / "cli-review.db"
    exit_code, stdout, stderr = _run_cli(
        "review",
        "--input",
        str(_fixture_path("funny_but_hollow.json")),
        "--dry-run",
        settings=Settings(database_path=database_path),
    )

    assert exit_code == 0
    assert stderr == ""
    assert '"manuscript_id": "funny-hollow-002"' in stdout
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT event_type FROM event_logs ORDER BY id DESC LIMIT 1"
        ).fetchone()

    assert row is not None
    assert row[0] == "dry_run_completed"


def test_cli_show_default_venue_prints_built_in_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()
    monkeypatch.setenv("GLORIOUS_MESS_DATABASE_PATH", str(tmp_path / "default-venue.db"))
    monkeypatch.setattr(sys, "argv", ["glorious_mess_reviewer", "show-default-venue"])

    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        runpy.run_module("glorious_mess_reviewer", run_name="__main__")

    assert stderr.getvalue() == ""
    payload = json.loads(stdout.getvalue())
    assert payload["venue_name"] == "S.H.I.T Initial Screening Desk"
    assert payload["preset_name"] == "shit-screening-default"
    assert payload["recommendation_policy"]["advance_to_full_review_min_final_score"] == 4.2


def test_cli_show_default_venue_supports_builtin_presets(tmp_path: Path) -> None:
    exit_code, stdout, stderr = _run_cli(
        "show-default-venue",
        "--preset",
        "shit-hardcore-screening",
        settings=Settings(database_path=tmp_path / "preset-venue.db"),
    )

    assert exit_code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["venue_name"] == "S.H.I.T Hardcore Screening Track"
    assert payload["preset_name"] == "shit-hardcore-screening"


def test_cli_review_output_flag_writes_result_file(tmp_path: Path) -> None:
    database_path = tmp_path / "cli-output.db"
    output_path = tmp_path / "review-output.json"
    exit_code, stdout, stderr = _run_cli(
        "review",
        "--input",
        str(_fixture_path("funny_but_hollow.json")),
        "--dry-run",
        "--output",
        str(output_path),
        settings=Settings(database_path=database_path),
    )

    assert exit_code == 0
    assert stderr == ""
    assert '"manuscript_id": "funny-hollow-002"' in stdout
    assert output_path.exists()
    saved_payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved_payload["manuscript_id"] == "funny-hollow-002"


def test_cli_review_reports_provider_failure_as_json(tmp_path: Path) -> None:
    exit_code, stdout, stderr = _run_cli(
        "review",
        "--input",
        str(_fixture_path("absurd_but_rigorous.json")),
        settings=Settings(
            database_path=tmp_path / "provider-failure.db",
            provider_backend="openai",
            openai_api_key=None,
        ),
    )

    assert exit_code == 2
    assert stdout == ""
    payload = json.loads(stderr)
    assert payload["error_code"] == "provider_failure"


def test_cli_review_reports_missing_input_as_json(tmp_path: Path) -> None:
    exit_code, stdout, stderr = _run_cli(
        "review",
        "--input",
        str(tmp_path / "missing.json"),
        "--dry-run",
        settings=Settings(database_path=tmp_path / "missing-input.db"),
    )

    assert exit_code == 1
    assert stdout == ""
    payload = json.loads(stderr)
    assert payload["error_code"] == "input_not_found"
    assert "missing.json" in payload["message"]


def test_cli_review_reports_invalid_input_as_json(tmp_path: Path) -> None:
    input_path = tmp_path / "invalid.json"
    input_path.write_text("{not-json", encoding="utf-8")

    exit_code, stdout, stderr = _run_cli(
        "review",
        "--input",
        str(input_path),
        "--dry-run",
        settings=Settings(database_path=tmp_path / "invalid-input.db"),
    )

    assert exit_code == 1
    assert stdout == ""
    payload = json.loads(stderr)
    assert payload["error_code"] == "invalid_input"
    assert payload["details"]["errors"]


def test_cli_full_review_persists_workflow_session(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "cli-full-review.db"
    monkeypatch.setattr(
        "glorious_mess_reviewer.cli.main.build_provider",
        lambda settings, log_degraded=False: MockLLMProvider(build_mock_registry()),
    )

    exit_code, stdout, stderr = _run_cli(
        "review",
        "--input",
        str(_fixture_path("absurd_but_rigorous.json")),
        settings=Settings(
            provider_backend="openai",
            openai_api_key="placeholder-key",
            database_path=database_path,
            minimum_reviewable_characters=200,
            store_raw_agent_outputs=True,
        ),
    )

    assert exit_code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["final_recommendation"] == "ADVANCE_TO_FULL_REVIEW"
    with sqlite3.connect(database_path) as connection:
        session_row = connection.execute(
            "SELECT workflow_id, status FROM workflow_sessions ORDER BY rowid DESC LIMIT 1"
        ).fetchone()

    assert session_row == ("screening.review.v1", "completed")


def test_cli_full_review_writes_markdown_intake_report(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "cli-full-review-report.db"
    report_path = tmp_path / "intake-report.md"
    monkeypatch.setattr(
        "glorious_mess_reviewer.cli.main.build_provider",
        lambda settings, log_degraded=False: MockLLMProvider(build_mock_registry()),
    )

    exit_code, stdout, stderr = _run_cli(
        "review",
        "--input",
        str(_fixture_path("absurd_but_rigorous.json")),
        "--report-output",
        str(report_path),
        settings=Settings(
            provider_backend="openai",
            openai_api_key="placeholder-key",
            database_path=database_path,
            minimum_reviewable_characters=200,
            store_raw_agent_outputs=True,
        ),
    )

    assert exit_code == 0
    assert stderr == ""
    assert json.loads(stdout)["final_recommendation"] == "ADVANCE_TO_FULL_REVIEW"
    report = report_path.read_text(encoding="utf-8")
    assert "# Venue-Fit Intake Report: absurd-rigorous-001" in report
    assert "## Gate Checklist" in report
    assert "## Confidence Map" in report
    assert "## Queue Triage" in report
    assert "| Lane | `submission_readiness` |" in report
    assert "| Primary gate | `ai_disclosure_integrity` |" in report
    assert "Weighted confidence" in report
    assert "panel evidence (manuscript)" in report
    assert "## Score Groups" in report
    assert "| Structure and Evidence | `strong` | 4.67 | `method_or_reasoning_legibility` |" in report
    assert "## Repair Targets" in report
    assert "| `method_or_reasoning_legibility` | `polish` | 4 | 0.86 | 1.10 |" in report
    assert "## Score Matrix" in report
    assert "real_shit_candidate" in report


def test_cli_report_output_requires_full_review(tmp_path: Path) -> None:
    report_path = tmp_path / "dry-run-report.md"

    exit_code, stdout, stderr = _run_cli(
        "review",
        "--input",
        str(_fixture_path("absurd_but_rigorous.json")),
        "--dry-run",
        "--report-output",
        str(report_path),
        settings=Settings(database_path=tmp_path / "dry-run-report.db"),
    )

    assert exit_code == 1
    assert stdout == ""
    payload = json.loads(stderr)
    assert payload["error_code"] == "report_requires_full_review"
    assert not report_path.exists()


def test_cli_risk_audit_runs_workflow_and_returns_result(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "cli-risk-audit.db"
    monkeypatch.setattr(
        "glorious_mess_reviewer.cli.main.build_provider",
        lambda settings, log_degraded=False: MockLLMProvider(build_mock_registry()),
    )

    payload_path = tmp_path / "risk-audit-input.json"
    payload = load_fixture("absurd_but_rigorous.json")
    payload["abstract"] = "This draft keeps saying weaponize the office workflow."
    payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    exit_code, stdout, stderr = _run_cli(
        "risk-audit",
        "--input",
        str(payload_path),
        settings=Settings(
            provider_backend="openai",
            openai_api_key="placeholder-key",
            database_path=database_path,
            minimum_reviewable_characters=200,
            store_raw_agent_outputs=True,
        ),
    )

    assert exit_code == 0
    assert stderr == ""
    result = json.loads(stdout)
    assert result["action"] == "FLAG_FOR_HUMAN_REVIEW"
    with sqlite3.connect(database_path) as connection:
        session_row = connection.execute(
            "SELECT workflow_id, status FROM workflow_sessions ORDER BY rowid DESC LIMIT 1"
        ).fetchone()

    assert session_row == ("screening.risk_audit.v1", "completed")


def test_cli_venue_fit_audit_runs_workflow_and_returns_result(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "cli-venue-fit.db"
    monkeypatch.setattr(
        "glorious_mess_reviewer.cli.main.build_provider",
        lambda settings, log_degraded=False: MockLLMProvider(build_mock_registry()),
    )

    exit_code, stdout, stderr = _run_cli(
        "venue-fit-audit",
        "--input",
        str(_fixture_path("absurd_but_rigorous.json")),
        settings=Settings(
            provider_backend="openai",
            openai_api_key="placeholder-key",
            database_path=database_path,
            minimum_reviewable_characters=200,
            store_raw_agent_outputs=True,
        ),
    )

    assert exit_code == 0
    assert stderr == ""
    result = json.loads(stdout)
    assert result["action"] == "STRONG_FIT"
    with sqlite3.connect(database_path) as connection:
        session_row = connection.execute(
            "SELECT workflow_id, status FROM workflow_sessions ORDER BY rowid DESC LIMIT 1"
        ).fetchone()

    assert session_row == ("screening.venue_fit_audit.v1", "completed")

def test_cli_show_review_reads_persisted_record(tmp_path: Path) -> None:
    database_path = tmp_path / "show-review.db"
    settings = Settings(
        provider_backend="mock",
        database_path=database_path,
        minimum_reviewable_characters=200,
        store_raw_agent_outputs=True,
    )
    store = SQLiteReviewStore(database_path)
    orchestrator = ReviewOrchestrator(
        settings=settings,
        provider=MockLLMProvider(build_mock_registry()),
        store=store,
    )
    asyncio.run(orchestrator.review(ManuscriptInput.model_validate(load_fixture("absurd_but_rigorous.json"))))

    with sqlite3.connect(database_path) as connection:
        run_id = connection.execute("SELECT run_id FROM review_runs ORDER BY created_at DESC LIMIT 1").fetchone()[0]

    exit_code, stdout, stderr = _run_cli(
        "show-review",
        "--run-id",
        run_id,
        settings=settings,
    )

    assert exit_code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["run_id"] == run_id
    assert payload["review"]["manuscript_id"] == "absurd-rigorous-001"


def test_cli_show_review_display_reads_projection(tmp_path: Path) -> None:
    database_path = tmp_path / "show-review-display.db"
    settings = Settings(
        provider_backend="mock",
        database_path=database_path,
        minimum_reviewable_characters=200,
        store_raw_agent_outputs=True,
    )
    store = SQLiteReviewStore(database_path)
    orchestrator = ReviewOrchestrator(
        settings=settings,
        provider=MockLLMProvider(build_mock_registry()),
        store=store,
    )
    asyncio.run(orchestrator.review(ManuscriptInput.model_validate(load_fixture("absurd_but_rigorous.json"))))

    with sqlite3.connect(database_path) as connection:
        run_id = connection.execute("SELECT run_id FROM review_runs ORDER BY created_at DESC LIMIT 1").fetchone()[0]

    exit_code, stdout, stderr = _run_cli(
        "show-review-display",
        "--run-id",
        run_id,
        settings=settings,
    )

    assert exit_code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["run_id"] == run_id
    assert payload["suggested_stage"] == "real_shit_candidate"
    assert payload["calibration_status"] == "high_confidence"
    assert payload["triage"]["queue_priority"] == 70
    assert payload["triage"]["lane"] == "submission_readiness"
    assert payload["triage"]["primary_gate"] == "ai_disclosure_integrity"
    assert payload["triage"]["action"] == "Add metadata.ai_use_statement before publishing the intake card."
    gates = {gate["name"]: gate for gate in payload["gates"]}
    assert gates["format_compliance"]["status"] == "pass"
    assert gates["citation_traceability"]["status"] == "pass"
    assert gates["ai_disclosure_integrity"]["status"] == "needs_review"
    assert gates["safety_notice_presence"]["status"] == "needs_review"
    assert payload["score_matrix"][0]["evidence"] == ["panel evidence (manuscript)"]
    assert payload["score_groups"][0]["group_id"] == "structure_and_evidence"
    assert payload["score_groups"][0]["status"] == "strong"
    assert payload["score_groups"][1]["dimensions"] == [
        "venue_fit",
        "zhenghuo_execution",
        "absurd_originality",
        "meme_to_argument_conversion",
    ]
    assert payload["score_groups"][1]["weakest_dimension"] == "absurd_originality"
    assert payload["score_groups"][1]["recommended_action"] == (
        "Keep the absurd framing disciplined while preserving payload."
    )
    assert payload["repair_targets"][0]["dimension"] == "method_or_reasoning_legibility"
    assert payload["repair_targets"][0]["priority_score"] == 1.1
    assert "raw_agent_outputs" not in payload


def test_cli_show_workflow_reads_persisted_session(tmp_path: Path) -> None:
    database_path = tmp_path / "show-workflow.db"
    settings = Settings(
        provider_backend="mock",
        database_path=database_path,
        minimum_reviewable_characters=200,
        store_raw_agent_outputs=True,
    )
    store = SQLiteReviewStore(database_path)
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

    exit_code, stdout, stderr = _run_cli(
        "show-workflow",
        "--session-id",
        session.session_id,
        settings=settings,
    )

    assert exit_code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["session_id"] == session.session_id
    assert payload["workflow_id"] == "screening.review.v1"


def test_cli_list_reviews_returns_summary_rows(tmp_path: Path) -> None:
    database_path = tmp_path / "list-reviews.db"
    settings = Settings(
        provider_backend="mock",
        database_path=database_path,
        minimum_reviewable_characters=200,
        store_raw_agent_outputs=True,
    )
    store = SQLiteReviewStore(database_path)
    orchestrator = ReviewOrchestrator(
        settings=settings,
        provider=MockLLMProvider(build_mock_registry()),
        store=store,
    )
    asyncio.run(orchestrator.review(ManuscriptInput.model_validate(load_fixture("absurd_but_rigorous.json"))))
    asyncio.run(orchestrator.review(ManuscriptInput.model_validate(load_fixture("funny_but_hollow.json"))))

    exit_code, stdout, stderr = _run_cli(
        "list-reviews",
        "--limit",
        "10",
        settings=settings,
    )

    assert exit_code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert len(payload) == 2
    assert payload[0]["manuscript_id"] == "funny-hollow-002"
    assert payload[0]["resolved_venue_profile"]["preset_name"] == "shit-screening-default"


def test_cli_list_review_displays_returns_queue_rows(tmp_path: Path) -> None:
    database_path = tmp_path / "list-review-displays.db"
    settings = Settings(
        provider_backend="mock",
        database_path=database_path,
        minimum_reviewable_characters=200,
        store_raw_agent_outputs=True,
    )
    store = SQLiteReviewStore(database_path)
    orchestrator = ReviewOrchestrator(
        settings=settings,
        provider=MockLLMProvider(build_mock_registry()),
        store=store,
    )
    asyncio.run(orchestrator.review(ManuscriptInput.model_validate(load_fixture("absurd_but_rigorous.json"))))
    asyncio.run(orchestrator.review(ManuscriptInput.model_validate(load_fixture("funny_but_hollow.json"))))

    exit_code, stdout, stderr = _run_cli(
        "list-review-displays",
        "--limit",
        "10",
        settings=settings,
    )

    assert exit_code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert len(payload) == 2
    assert payload[0]["manuscript_id"] == "funny-hollow-002"
    assert payload[0]["triage"]["lane"] == "author_revision"
    assert payload[0]["triage"]["queue_priority"] == 75
    assert payload[0]["top_repair_target"]["dimension"] == "result_payload"
    assert payload[0]["needs_review_gates"] == ["ai_disclosure_integrity", "safety_notice_presence"]


def test_cli_list_review_displays_can_sort_and_filter_queue(tmp_path: Path) -> None:
    database_path = tmp_path / "list-review-displays-sort.db"
    settings = Settings(
        provider_backend="mock",
        database_path=database_path,
        minimum_reviewable_characters=200,
        store_raw_agent_outputs=True,
    )
    store = SQLiteReviewStore(database_path)
    orchestrator = ReviewOrchestrator(
        settings=settings,
        provider=MockLLMProvider(build_mock_registry()),
        store=store,
    )
    risky = load_fixture("absurd_but_rigorous.json")
    risky["manuscript_id"] = "risk-sort-cli-001"
    risky["abstract"] = "This draft repeatedly says it will weaponize office-chair logistics."
    asyncio.run(orchestrator.review(ManuscriptInput.model_validate(risky)))
    asyncio.run(orchestrator.review(ManuscriptInput.model_validate(load_fixture("funny_but_hollow.json"))))

    exit_code, stdout, stderr = _run_cli(
        "list-review-displays",
        "--sort",
        "queue_priority",
        "--lane",
        "human_risk_review",
        "--limit",
        "10",
        settings=settings,
    )

    assert exit_code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert len(payload) == 1
    assert payload[0]["manuscript_id"] == "risk-sort-cli-001"
    assert payload[0]["triage"]["lane"] == "human_risk_review"
    assert payload[0]["triage"]["queue_priority"] == 100


def test_cli_list_review_displays_can_sort_by_repair_priority(tmp_path: Path) -> None:
    database_path = tmp_path / "list-review-displays-repair-sort.db"
    settings = Settings(
        provider_backend="mock",
        database_path=database_path,
        minimum_reviewable_characters=200,
        store_raw_agent_outputs=True,
    )
    store = SQLiteReviewStore(database_path)
    orchestrator = ReviewOrchestrator(
        settings=settings,
        provider=MockLLMProvider(build_mock_registry()),
        store=store,
    )
    asyncio.run(orchestrator.review(ManuscriptInput.model_validate(load_fixture("funny_but_hollow.json"))))
    asyncio.run(orchestrator.review(ManuscriptInput.model_validate(load_fixture("absurd_but_rigorous.json"))))

    exit_code, stdout, stderr = _run_cli(
        "list-review-displays",
        "--sort",
        "repair_priority",
        "--limit",
        "10",
        settings=settings,
    )

    assert exit_code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert [item["manuscript_id"] for item in payload] == ["funny-hollow-002", "absurd-rigorous-001"]
    assert payload[0]["top_repair_target"]["dimension"] == "result_payload"
    assert payload[0]["top_repair_target"]["priority_score"] > payload[1]["top_repair_target"]["priority_score"]


def test_cli_review_display_overview_returns_queue_counters(tmp_path: Path) -> None:
    database_path = tmp_path / "review-display-overview.db"
    settings = Settings(
        provider_backend="mock",
        database_path=database_path,
        minimum_reviewable_characters=200,
        store_raw_agent_outputs=True,
    )
    store = SQLiteReviewStore(database_path)
    orchestrator = ReviewOrchestrator(
        settings=settings,
        provider=MockLLMProvider(build_mock_registry()),
        store=store,
    )
    risky = load_fixture("absurd_but_rigorous.json")
    risky["manuscript_id"] = "risk-overview-cli-001"
    risky["abstract"] = "This draft repeatedly says it will weaponize office-chair logistics."
    asyncio.run(orchestrator.review(ManuscriptInput.model_validate(risky)))
    asyncio.run(orchestrator.review(ManuscriptInput.model_validate(load_fixture("funny_but_hollow.json"))))
    asyncio.run(orchestrator.review(ManuscriptInput.model_validate(load_fixture("absurd_but_rigorous.json"))))

    exit_code, stdout, stderr = _run_cli(
        "review-display-overview",
        "--limit",
        "10",
        settings=settings,
    )

    assert exit_code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["total_reviews"] == 3
    assert payload["lane_counts"]["human_risk_review"] == 1
    assert payload["lane_counts"]["author_revision"] == 1
    assert payload["lane_counts"]["submission_readiness"] == 1
    assert payload["needs_human_review"] == 1
    assert payload["gate_counts"]["ai_disclosure_integrity"] == 3
    assert payload["top_repair_hotspots"][0]["dimension"] == "result_payload"


def test_cli_list_workflows_returns_registered_metadata(tmp_path: Path) -> None:
    exit_code, stdout, stderr = _run_cli(
        "list-workflows",
        settings=Settings(database_path=tmp_path / "list-workflows.db"),
    )

    assert exit_code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    workflow_ids = {item["workflow_id"] for item in payload}
    assert "screening.review.v1" in workflow_ids
    assert "screening.risk_audit.v1" in workflow_ids
    assert "screening.venue_fit_audit.v1" in workflow_ids
    review_workflow = next(item for item in payload if item["workflow_id"] == "screening.review.v1")
    assert ["panel.evidence", "panel.value"] in review_workflow["parallel_groups"]
    assert "decision.review_output" in review_workflow["artifact_keys"]


def test_cli_list_limit_matches_public_api_bounds(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc_info:
        _run_cli(
            "list-reviews",
            "--limit",
            "0",
            settings=Settings(database_path=tmp_path / "bad-list-limit.db"),
        )

    assert exc_info.value.code == 2


def test_cli_list_workflow_sessions_returns_persisted_audit_rows(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "workflow-session-list.db"
    monkeypatch.setattr(
        "glorious_mess_reviewer.cli.main.build_provider",
        lambda settings, log_degraded=False: MockLLMProvider(build_mock_registry()),
    )
    settings = Settings(
        provider_backend="openai",
        openai_api_key="placeholder-key",
        database_path=database_path,
        minimum_reviewable_characters=200,
        store_raw_agent_outputs=True,
    )

    _run_cli("risk-audit", "--input", str(_fixture_path("absurd_but_rigorous.json")), settings=settings)
    exit_code, stdout, stderr = _run_cli(
        "list-workflow-sessions",
        "--workflow-id",
        "screening.risk_audit.v1",
        "--manuscript-id",
        "absurd-rigorous-001",
        settings=settings,
    )

    assert exit_code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert len(payload) == 1
    assert payload[0]["workflow_id"] == "screening.risk_audit.v1"
    assert payload[0]["manuscript_id"] == "absurd-rigorous-001"
    assert payload[0]["final_output_type"] == "risk_audit_output"


def test_cli_doctor_reports_dry_run_ready_without_provider(tmp_path: Path) -> None:
    exit_code, stdout, stderr = _run_cli(
        "doctor",
        settings=Settings(
            provider_backend="openai",
            openai_api_key=None,
            database_path=tmp_path / "doctor.db",
        ),
    )

    assert exit_code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["status"] == "degraded"
    assert payload["database_ok"] is True
    assert payload["dry_run_ready"] is True
    assert payload["provider_configured"] is False
    assert payload["full_review_ready"] is False
    assert payload["default_model"] == "gpt-4o-mini"


def test_cli_doctor_require_provider_returns_nonzero_when_provider_missing(tmp_path: Path) -> None:
    exit_code, stdout, stderr = _run_cli(
        "doctor",
        "--require-provider",
        settings=Settings(
            provider_backend="openai",
            openai_api_key=None,
            database_path=tmp_path / "doctor-require-provider.db",
        ),
    )

    assert exit_code == 1
    assert stderr == ""
    assert json.loads(stdout)["full_review_ready"] is False


def test_cli_doctor_reports_provider_diagnostic_failure_as_json(tmp_path: Path, monkeypatch) -> None:
    def fail_provider(*args, **kwargs):
        raise RuntimeError("bad provider config")

    monkeypatch.setattr("glorious_mess_reviewer.cli.main.build_provider", fail_provider)

    exit_code, stdout, stderr = _run_cli(
        "doctor",
        settings=Settings(
            provider_backend="openai",
            openai_api_key="placeholder-key",
            database_path=tmp_path / "doctor-provider-failure.db",
        ),
    )

    assert exit_code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["status"] == "degraded"
    assert payload["provider_configured"] is False
    assert payload["checks"][1]["status"] == "fail"
    assert "bad provider config" in payload["checks"][1]["message"]


def test_cli_new_manuscript_prints_valid_payload_and_writes_file(tmp_path: Path) -> None:
    output_path = tmp_path / "starter.json"
    exit_code, stdout, stderr = _run_cli(
        "new-manuscript",
        "--manuscript-id",
        "starter-001",
        "--output",
        str(output_path),
        settings=Settings(database_path=tmp_path / "new-manuscript.db"),
    )

    assert exit_code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    manuscript = ManuscriptInput.model_validate(payload)
    assert manuscript.manuscript_id == "starter-001"
    assert "Conclusion" in manuscript.body
    assert "Limitations" in manuscript.body
    assert manuscript.metadata is not None
    assert manuscript.metadata["submission_track"] == "rigorous_argument"
    assert manuscript.metadata["routing_stage"] == "petri_dish"
    assert "ai_use_statement" in manuscript.metadata
    assert "safety_notice" in manuscript.metadata
    assert output_path.exists()
    assert json.loads(output_path.read_text(encoding="utf-8")) == payload


def test_cli_new_manuscript_rejects_blank_identifier(tmp_path: Path) -> None:
    exit_code, stdout, stderr = _run_cli(
        "new-manuscript",
        "--manuscript-id",
        "   ",
        settings=Settings(database_path=tmp_path / "new-manuscript-invalid.db"),
    )

    assert exit_code == 1
    assert stdout == ""
    payload = json.loads(stderr)
    assert payload["error_code"] == "invalid_manuscript_id"


def test_cli_new_manuscript_trims_identifier(tmp_path: Path) -> None:
    exit_code, stdout, stderr = _run_cli(
        "new-manuscript",
        "--manuscript-id",
        "  starter-002  ",
        settings=Settings(database_path=tmp_path / "new-manuscript-trim.db"),
    )

    assert exit_code == 0
    assert stderr == ""
    assert json.loads(stdout)["manuscript_id"] == "starter-002"


def test_cli_benchmark_dry_run_writes_json_and_markdown_reports(tmp_path: Path) -> None:
    json_output = tmp_path / "benchmark.json"
    markdown_output = tmp_path / "benchmark.md"

    exit_code, stdout, stderr = _run_cli(
        "benchmark",
        "--mode",
        "dry-run",
        "--limit",
        "2",
        "--output",
        str(json_output),
        "--markdown-output",
        str(markdown_output),
        settings=Settings(database_path=tmp_path / "benchmark.db"),
    )

    assert exit_code == 0
    assert stderr == ""
    payload = json.loads(stdout)
    assert payload["mode"] == "dry-run"
    assert payload["summary"]["total_cases"] == 2
    assert payload["summary"]["ok_cases"] == 2
    assert json.loads(json_output.read_text(encoding="utf-8")) == payload
    assert "Benchmark Report" in markdown_output.read_text(encoding="utf-8")


def test_cli_benchmark_reports_invalid_suite_as_json(tmp_path: Path) -> None:
    exit_code, stdout, stderr = _run_cli(
        "benchmark",
        "--suite",
        str(tmp_path / "missing-suite.json"),
        settings=Settings(database_path=tmp_path / "benchmark-invalid.db"),
    )

    assert exit_code == 1
    assert stdout == ""
    payload = json.loads(stderr)
    assert payload["error_code"] == "invalid_benchmark_suite"
    assert payload["details"]["path"].endswith("missing-suite.json")
