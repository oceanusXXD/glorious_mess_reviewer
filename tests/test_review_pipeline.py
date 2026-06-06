"""Focused regression tests for review pipeline precheck merging."""

from __future__ import annotations

from pathlib import Path

from glorious_mess_reviewer.config import Settings
from glorious_mess_reviewer.orchestrator import ReviewOrchestrator
from glorious_mess_reviewer.schemas import ManuscriptInput, PrecheckDecision, PrecheckOutput, VenueProfile
from glorious_mess_reviewer.storage import SQLiteReviewStore


def _build_orchestrator(database_path: Path) -> ReviewOrchestrator:
    settings = Settings(database_path=database_path)
    return ReviewOrchestrator(
        settings=settings,
        provider=None,
        store=SQLiteReviewStore(database_path),
    )


def test_merge_precheck_normalizes_decision_when_local_risk_flags_survive(tmp_path: Path) -> None:
    orchestrator = _build_orchestrator(tmp_path / "review-pipeline.db")

    local = PrecheckOutput(
        decision=PrecheckDecision.REVISION_REQUIRED,
        minimum_reviewable=True,
        hard_failures=[],
        missing_sections=[],
        risk_flags=["risk_dangerous_actionable"],
        notes=["Local regex precheck found risky phrasing."],
    )
    llm = PrecheckOutput(
        decision=PrecheckDecision.PASS,
        minimum_reviewable=True,
        hard_failures=[],
        missing_sections=[],
        risk_flags=[],
        notes=["LLM thought the submission looked reviewable."],
    )

    merged = orchestrator._merge_precheck(local, llm)

    assert merged.risk_flags == ["risk_dangerous_actionable"]
    assert merged.decision == PrecheckDecision.REVISION_REQUIRED


def test_local_precheck_flags_exploitative_sexual_content(tmp_path: Path) -> None:
    orchestrator = _build_orchestrator(tmp_path / "review-pipeline-risk.db")
    manuscript = ManuscriptInput(
        manuscript_id="m-risk-1",
        title="On revenge porn as a filing system",
        abstract="This cursed draft says revenge porn repeatedly.",
        body="Conclusion\nLimitations\n" + ("revenge porn is mentioned as a tactic. " * 20),
    )

    precheck = orchestrator._build_local_precheck(
        manuscript,
        VenueProfile.default_screening_profile(minimum_reviewable_characters=20),
    )

    assert "risk_exploitative_sexual_content" in precheck.risk_flags
