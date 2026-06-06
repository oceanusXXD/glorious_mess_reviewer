"""Venue profile behavior tests."""

import asyncio
import json
from pathlib import Path

from glorious_mess_reviewer.config import Settings
from glorious_mess_reviewer.orchestrator import ReviewOrchestrator
from glorious_mess_reviewer.schemas import ManuscriptInput, VenueProfile
from glorious_mess_reviewer.storage import SQLiteReviewStore


def test_custom_venue_length_threshold_affects_precheck(tmp_path) -> None:
    settings = Settings(provider_backend="mock", database_path=tmp_path / "venue-threshold.db")
    orchestrator = ReviewOrchestrator(settings=settings, provider=None, store=SQLiteReviewStore(settings.database_path))
    venue = VenueProfile.default_screening_profile()
    venue.minimum_reviewable_characters = 10
    manuscript = ManuscriptInput(
        manuscript_id="venue-threshold-1",
        title="t",
        abstract="a",
        body="12345678901",
        venue_profile=venue,
    )
    result = asyncio.run(orchestrator.dry_run(manuscript))
    assert "body_too_short_for_review" not in result.precheck.hard_failures


def test_documented_custom_venue_profile_example_validates() -> None:
    path = Path(__file__).resolve().parents[1] / "docs" / "examples" / "custom-venue-profile.json"
    profile = VenueProfile.model_validate(json.loads(path.read_text(encoding="utf-8")))

    assert profile.venue_name == "Custom S.H.I.T Community Screening Desk"
    assert profile.recommendation_policy.advance_to_full_review_min_final_score == 4.1
