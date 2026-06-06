"""Benchmark report coverage."""

from __future__ import annotations

from pathlib import Path

from glorious_mess_reviewer.benchmark import (
    BenchmarkRunOptions,
    _distill_benchmark_sediment,
    render_benchmark_markdown,
    run_benchmark_suite,
)
from glorious_mess_reviewer.config import Settings


def test_benchmark_suite_runs_deterministic_dry_run(tmp_path: Path) -> None:
    report = run_benchmark_suite(
        settings=Settings(database_path=tmp_path / "benchmark-dry-run.db"),
        suite_path=Path("docs/examples/benchmark-suite.json"),
        options=BenchmarkRunOptions(mode="dry-run"),
    )

    assert report["suite_name"] == "S.H.I.T screening fixture benchmark"
    assert report["mode"] == "dry-run"
    assert report["summary"]["total_cases"] == 7
    assert report["summary"]["ok_cases"] == 7
    assert report["summary"]["accepted_match_rate"] == 1.0
    assert report["summary"]["risk_flags_match_rate"] == 1.0
    cautionary_case = next(
        case for case in report["cases"] if case["case_id"] == "cautionary_risk_language_should_not_false_positive"
    )
    assert cautionary_case["actual_risk_flags"] == []


def test_benchmark_markdown_highlights_summary(tmp_path: Path) -> None:
    report = run_benchmark_suite(
        settings=Settings(database_path=tmp_path / "benchmark-markdown.db"),
        suite_path=Path("docs/examples/benchmark-suite.json"),
        options=BenchmarkRunOptions(mode="dry-run", limit=1),
    )

    markdown = render_benchmark_markdown(report)

    assert "# Benchmark Report: S.H.I.T screening fixture benchmark" in markdown
    assert "| Case | Expected | Actual | Baseline | Delta | Status | Latency ms |" in markdown


def test_benchmark_markdown_explains_review_baseline_delta() -> None:
    markdown = render_benchmark_markdown(
        {
            "suite_name": "delta suite",
            "mode": "review",
            "settings": {
                "default_model": "mock-model",
                "provider_backend": "mock",
                "openai_api_style": "responses",
            },
            "summary": {
                "total_cases": 3,
                "ok_cases": 3,
                "recommendation_accuracy": 0.67,
                "baseline_recommendation_accuracy": 0.33,
                "recommendation_accuracy_lift": 0.34,
                "baseline_delta_counts": {
                    "both_correct": 0,
                    "workflow_win": 1,
                    "baseline_win": 1,
                    "both_missed": 1,
                    "unmeasured": 0,
                },
                "mean_workflow_step_count": 6.0,
            },
            "cases": [
                {
                    "case_id": "workflow-wins",
                    "expected_recommendation": "ADVANCE_TO_FULL_REVIEW",
                    "actual_recommendation": "ADVANCE_TO_FULL_REVIEW",
                    "baseline_recommendation": "REVISION_REQUIRED_BEFORE_REVIEW",
                    "baseline_delta": "workflow_win",
                    "status": "ok",
                    "latency_ms": 123,
                },
                {
                    "case_id": "baseline-wins",
                    "expected_recommendation": "REVISION_REQUIRED_BEFORE_REVIEW",
                    "actual_recommendation": "REJECT_AS_EMPTY_GIMMICK",
                    "baseline_recommendation": "REVISION_REQUIRED_BEFORE_REVIEW",
                    "baseline_delta": "baseline_win",
                    "status": "ok",
                    "latency_ms": 80,
                },
                {
                    "case_id": "both-missed",
                    "expected_recommendation": "ESCALATE_FOR_HUMAN_RISK_CHECK",
                    "actual_recommendation": "REVISION_REQUIRED_BEFORE_REVIEW",
                    "baseline_recommendation": "ADVANCE_TO_FULL_REVIEW",
                    "baseline_delta": "both_missed",
                    "status": "ok",
                    "latency_ms": 90,
                },
            ],
        }
    )

    assert "- Workflow-win cases: `1`" in markdown
    assert "- Baseline-win cases: `1`" in markdown
    assert "- Both-missed cases: `1`" in markdown
    assert "- Mean workflow steps: `6.0`" in markdown
    assert "| workflow-wins | ADVANCE_TO_FULL_REVIEW | ADVANCE_TO_FULL_REVIEW | REVISION_REQUIRED_BEFORE_REVIEW | workflow_win | ok | 123 |" in markdown


def test_review_benchmark_summary_counts_baseline_deltas() -> None:
    summary = _distill_benchmark_sediment(
        [
            {
                "case_id": "workflow-wins",
                "status": "ok",
                "latency_ms": 100,
                "expected_recommendation": "ADVANCE_TO_FULL_REVIEW",
                "recommendation_match": True,
                "baseline_recommendation_match": False,
                "baseline_delta": "workflow_win",
                "risk_gate_match": True,
                "workflow_step_count": 6,
                "skipped_steps": [],
            },
            {
                "case_id": "baseline-wins",
                "status": "ok",
                "latency_ms": 200,
                "expected_recommendation": "REVISION_REQUIRED_BEFORE_REVIEW",
                "recommendation_match": False,
                "baseline_recommendation_match": True,
                "baseline_delta": "baseline_win",
                "risk_gate_match": True,
                "workflow_step_count": 5,
                "skipped_steps": ["panel.meta"],
            },
            {
                "case_id": "both-missed",
                "status": "ok",
                "latency_ms": 300,
                "expected_recommendation": "ESCALATE_FOR_HUMAN_RISK_CHECK",
                "recommendation_match": False,
                "baseline_recommendation_match": False,
                "baseline_delta": "both_missed",
                "risk_gate_match": False,
                "workflow_step_count": 4,
                "skipped_steps": ["panel.evidence", "panel.value"],
            },
        ],
        mode="review",
    )

    assert summary["baseline_delta_counts"] == {
        "both_correct": 0,
        "workflow_win": 1,
        "baseline_win": 1,
        "both_missed": 1,
        "unmeasured": 0,
    }
    assert summary["workflow_win_cases"] == ["workflow-wins"]
    assert summary["baseline_win_cases"] == ["baseline-wins"]
    assert summary["both_missed_cases"] == ["both-missed"]
    assert summary["mean_workflow_step_count"] == 5.0
    assert summary["mean_skipped_step_count"] == 1.0
