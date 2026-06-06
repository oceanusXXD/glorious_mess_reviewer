"""Benchmark helpers for comparing intake baselines with full screening."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from pydantic import BaseModel, Field

from glorious_mess_reviewer.config import Settings
from glorious_mess_reviewer.providers import ProviderError
from glorious_mess_reviewer.runtime import build_review_service
from glorious_mess_reviewer.schemas import (
    ManuscriptInput,
    RecommendationLabel,
    WorkflowStepStatus,
)

BenchmarkMode = Literal["dry-run", "review"]


class BenchmarkCase(BaseModel):
    """One benchmark case loaded from a suite file."""

    case_id: str
    input_path: str
    description: str = ""
    overrides: dict[str, Any] = Field(default_factory=dict)
    expected_recommendation: RecommendationLabel | None = None
    expected_accepted_for_full_review: bool | None = None
    expected_risk_flags: list[str] = Field(default_factory=list)
    expected_risk_gate: bool | None = None


class BenchmarkSuite(BaseModel):
    """Benchmark suite descriptor."""

    suite_name: str
    minimum_reviewable_characters: int | None = Field(default=None, gt=0)
    cases: list[BenchmarkCase]


@dataclass(frozen=True)
class BenchmarkRunOptions:
    """Runtime options for one benchmark run."""

    mode: BenchmarkMode = "dry-run"
    limit: int | None = None


def load_benchmark_suite(path: Path) -> BenchmarkSuite:
    """Load a benchmark suite descriptor from disk."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    return BenchmarkSuite.model_validate(payload)


def run_benchmark_suite(
    *,
    settings: Settings,
    suite_path: Path,
    options: BenchmarkRunOptions,
) -> dict[str, Any]:
    """Run a benchmark suite and return a JSON-serializable report."""

    return asyncio.run(_run_benchmark_suite(settings=settings, suite_path=suite_path, options=options))


async def _run_benchmark_suite(
    *,
    settings: Settings,
    suite_path: Path,
    options: BenchmarkRunOptions,
) -> dict[str, Any]:
    suite = load_benchmark_suite(suite_path)
    if suite.minimum_reviewable_characters is not None:
        settings = settings.model_copy(
            update={"minimum_reviewable_characters": suite.minimum_reviewable_characters}
        )
    selected_cases = suite.cases[: options.limit] if options.limit is not None else suite.cases
    service = build_review_service(settings, provider=None) if options.mode == "dry-run" else build_review_service(settings)

    fermentation_receipts: list[dict[str, Any]] = []
    for case in selected_cases:
        fermentation_receipts.append(
            await _ferment_case(
                settings=settings,
                suite_path=suite_path,
                service=service,
                case=case,
                mode=options.mode,
            )
        )

    summary = _distill_benchmark_sediment(fermentation_receipts, mode=options.mode)
    return {
        "suite_name": suite.suite_name,
        "mode": options.mode,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "settings": {
            "provider_backend": settings.provider_backend,
            "openai_api_style": settings.openai_api_style,
            "default_model": settings.default_model,
            "minimum_reviewable_characters": settings.minimum_reviewable_characters,
        },
        "summary": summary,
        "cases": fermentation_receipts,
    }


async def _ferment_case(
    *,
    settings: Settings,
    suite_path: Path,
    service,
    case: BenchmarkCase,
    mode: BenchmarkMode,
) -> dict[str, Any]:
    started = perf_counter()
    manuscript = _load_case_manuscript(suite_path=suite_path, case=case)
    dry_latrine_recommendation = _dry_latrine_baseline(settings=settings, manuscript=manuscript)
    fermentation_receipt: dict[str, Any] = {
        "case_id": case.case_id,
        "description": case.description,
        "manuscript_id": manuscript.manuscript_id,
        "expected_recommendation": case.expected_recommendation.value if case.expected_recommendation else None,
        "expected_accepted_for_full_review": case.expected_accepted_for_full_review,
        "baseline_recommendation": dry_latrine_recommendation,
        "mode": mode,
    }

    try:
        if mode == "dry-run":
            dry_run = await service.dry_run(manuscript)
            fermentation_receipt.update(
                {
                    "status": "ok",
                    "actual_accepted_for_full_review": dry_run.accepted_for_full_review,
                    "actual_risk_flags": dry_run.precheck.risk_flags,
                    "accepted_match": _match_or_abstain(
                        dry_run.accepted_for_full_review,
                        case.expected_accepted_for_full_review,
                    ),
                    "risk_flags_match": set(case.expected_risk_flags) == set(dry_run.precheck.risk_flags),
                }
            )
        else:
            review = await service.review(manuscript)
            workflow = service.get_workflow_session(review.workflow_session_id)
            risk_gate_observed = _risk_gate_smell_detected(workflow)
            recommendation_match = _match_or_abstain(
                review.final_recommendation,
                case.expected_recommendation,
            )
            baseline_recommendation_match = _match_or_abstain(
                dry_latrine_recommendation,
                case.expected_recommendation.value if case.expected_recommendation else None,
            )
            fermentation_receipt.update(
                {
                    "status": "ok",
                    "actual_recommendation": review.final_recommendation.value,
                    "actual_final_score": review.final_score,
                    "actual_risk_flags": review.risk_flags,
                    "risk_gate_observed": risk_gate_observed,
                    "recommendation_match": recommendation_match,
                    "baseline_recommendation_match": baseline_recommendation_match,
                    "baseline_delta": _baseline_delta(recommendation_match, baseline_recommendation_match),
                    "risk_gate_match": _match_or_abstain(risk_gate_observed, case.expected_risk_gate),
                    "workflow_step_count": len(workflow.steps) if workflow else None,
                    "skipped_steps": [
                        step.node_id
                        for step in (workflow.steps if workflow else [])
                        if step.status == WorkflowStepStatus.skipped
                    ],
                }
            )
    except ProviderError as exc:
        fermentation_receipt.update({"status": "provider_error", "error": str(exc)})
    except Exception as exc:  # pragma: no cover - surfaced in benchmark output
        fermentation_receipt.update({"status": "error", "error": f"{exc.__class__.__name__}: {exc}"})

    fermentation_receipt["latency_ms"] = int((perf_counter() - started) * 1000)
    return fermentation_receipt


def render_benchmark_markdown(report: dict[str, Any]) -> str:
    """Render a benchmark report as a compact Markdown artifact."""

    summary = report["summary"]
    lines = [
        f"# Benchmark Report: {report['suite_name']}",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Model: `{report['settings']['default_model']}`",
        f"- Provider: `{report['settings']['provider_backend']}` / `{report['settings']['openai_api_style']}`",
        f"- Cases: `{summary['total_cases']}`",
        f"- OK cases: `{summary['ok_cases']}`",
    ]
    if "recommendation_accuracy" in summary:
        lines.extend(
            [
                f"- Recommendation accuracy: `{summary['recommendation_accuracy']}`",
                f"- Intake-only baseline accuracy: `{summary['baseline_recommendation_accuracy']}`",
                f"- Accuracy lift: `{summary['recommendation_accuracy_lift']}`",
            ]
        )
    if "baseline_delta_counts" in summary:
        delta_counts = summary["baseline_delta_counts"]
        lines.extend(
            [
                f"- Workflow-win cases: `{delta_counts['workflow_win']}`",
                f"- Baseline-win cases: `{delta_counts['baseline_win']}`",
                f"- Both-missed cases: `{delta_counts['both_missed']}`",
                f"- Mean workflow steps: `{summary['mean_workflow_step_count']}`",
            ]
        )
    if "accepted_match_rate" in summary:
        lines.extend(
            [
                f"- Accepted-for-review match rate: `{summary['accepted_match_rate']}`",
                f"- Risk-flag coverage rate: `{summary['risk_flags_match_rate']}`",
            ]
        )

    lines.extend(
        [
            "",
            "| Case | Expected | Actual | Baseline | Delta | Status | Latency ms |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for case in report["cases"]:
        actual = case.get("actual_recommendation")
        if actual is None and "actual_accepted_for_full_review" in case:
            actual = f"accepted={case['actual_accepted_for_full_review']}"
        lines.append(
            "| {case_id} | {expected} | {actual} | {baseline} | {delta} | {status} | {latency} |".format(
                case_id=case["case_id"],
                expected=case.get("expected_recommendation") or case.get("expected_accepted_for_full_review"),
                actual=actual,
                baseline=case.get("baseline_recommendation"),
                delta=case.get("baseline_delta") or "",
                status=case["status"],
                latency=case["latency_ms"],
            )
        )
    lines.append("")
    return "\n".join(lines)


def _load_case_manuscript(*, suite_path: Path, case: BenchmarkCase) -> ManuscriptInput:
    input_path = (suite_path.parent / case.input_path).resolve()
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    payload.update(case.overrides)
    return ManuscriptInput.model_validate(payload)


def _dry_latrine_baseline(*, settings: Settings, manuscript: ManuscriptInput) -> str:
    """Simple baseline: uses obvious intake signals, not panel scoring."""

    text = f"{manuscript.title}\n{manuscript.abstract}\n{manuscript.body}".lower()
    if any(marker in text for marker in ("weaponize", "build a bomb", "doxx", "fake passport")):
        return RecommendationLabel.ESCALATE_FOR_HUMAN_RISK_CHECK.value
    if not manuscript.title or not manuscript.abstract or not manuscript.body:
        return RecommendationLabel.REVISION_REQUIRED_BEFORE_REVIEW.value
    if len(manuscript.body) < settings.minimum_reviewable_characters:
        return RecommendationLabel.REVISION_REQUIRED_BEFORE_REVIEW.value
    return RecommendationLabel.REVISION_REQUIRED_BEFORE_REVIEW.value


def _risk_gate_smell_detected(workflow) -> bool:
    if workflow is None:
        return False
    for step in workflow.steps:
        if step.node_id in {"panel.evidence", "panel.value", "panel.meta"} and step.details:
            if step.details.get("reason") == "risk_gate":
                return True
    return False


def _distill_benchmark_sediment(fermentation_receipts: list[dict[str, Any]], *, mode: BenchmarkMode) -> dict[str, Any]:
    ok_cases = [case for case in fermentation_receipts if case["status"] == "ok"]
    sediment: dict[str, Any] = {
        "total_cases": len(fermentation_receipts),
        "ok_cases": len(ok_cases),
        "error_cases": len(fermentation_receipts) - len(ok_cases),
        "mean_latency_ms": round(
            sum(case["latency_ms"] for case in fermentation_receipts) / max(len(fermentation_receipts), 1),
            2,
        ),
    }
    if mode == "review":
        measured = [case for case in ok_cases if case.get("expected_recommendation") is not None]
        baseline_measured = [case for case in measured if case.get("baseline_recommendation") is not None]
        recommendation_accuracy = _fermentation_rate(case.get("recommendation_match") is True for case in measured)
        baseline_accuracy = _fermentation_rate(
            case.get("baseline_recommendation_match") is True for case in baseline_measured
        )
        sediment.update(
            {
                "recommendation_accuracy": recommendation_accuracy,
                "baseline_recommendation_accuracy": baseline_accuracy,
                "recommendation_accuracy_lift": round(recommendation_accuracy - baseline_accuracy, 4),
                "baseline_delta_counts": _baseline_delta_counts(ok_cases),
                "workflow_win_cases": _cases_with_delta(ok_cases, "workflow_win"),
                "baseline_win_cases": _cases_with_delta(ok_cases, "baseline_win"),
                "both_missed_cases": _cases_with_delta(ok_cases, "both_missed"),
                "mean_workflow_step_count": _mean_numeric(case.get("workflow_step_count") for case in ok_cases),
                "mean_skipped_step_count": _mean_numeric(len(case.get("skipped_steps", [])) for case in ok_cases),
                "risk_gate_match_rate": _fermentation_rate(
                    case.get("risk_gate_match") is True
                    for case in ok_cases
                    if case.get("risk_gate_match") is not None
                ),
            }
        )
    else:
        sediment.update(
            {
                "accepted_match_rate": _fermentation_rate(
                    case.get("accepted_match") is True
                    for case in ok_cases
                    if case.get("accepted_match") is not None
                ),
                "risk_flags_match_rate": _fermentation_rate(case.get("risk_flags_match") is True for case in ok_cases),
            }
        )
    return sediment


def _match_or_abstain(actual: object, expected: object | None) -> bool | None:
    if expected is None:
        return None
    return actual == expected


def _baseline_delta(recommendation_match: bool | None, baseline_match: bool | None) -> str:
    if recommendation_match is None or baseline_match is None:
        return "unmeasured"
    if recommendation_match and baseline_match:
        return "both_correct"
    if recommendation_match and not baseline_match:
        return "workflow_win"
    if not recommendation_match and baseline_match:
        return "baseline_win"
    return "both_missed"


def _baseline_delta_counts(cases: list[dict[str, Any]]) -> dict[str, int]:
    labels = ("both_correct", "workflow_win", "baseline_win", "both_missed", "unmeasured")
    return {label: sum(1 for case in cases if case.get("baseline_delta") == label) for label in labels}


def _cases_with_delta(cases: list[dict[str, Any]], delta: str) -> list[str]:
    return [case["case_id"] for case in cases if case.get("baseline_delta") == delta]


def _mean_numeric(values) -> float:
    sediment = [float(value) for value in values if value is not None]
    if not sediment:
        return 0.0
    return round(sum(sediment) / len(sediment), 2)


def _fermentation_rate(values) -> float:
    sediment = list(values)
    if not sediment:
        return 0.0
    return round(sum(1 for value in sediment if value) / len(sediment), 4)
