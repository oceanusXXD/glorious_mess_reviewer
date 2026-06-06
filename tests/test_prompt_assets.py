"""Prompt asset tests for venue guidance and few-shot calibration."""

from glorious_mess_reviewer.prompts.few_shots import build_venue_examples_text
from glorious_mess_reviewer.prompts.venue_guidance import build_venue_guidance_text
from glorious_mess_reviewer.schemas import VenuePresetName, VenueProfile


def test_few_shot_examples_change_by_track() -> None:
    default_profile = VenueProfile.default_screening_profile()
    hardcore_profile = VenueProfile.from_builtin_preset(VenuePresetName.SHIT_HARDCORE_SCREENING)
    abstract_profile = VenueProfile.from_builtin_preset(VenuePresetName.SHIT_ABSTRACT_SCREENING)

    default_text = build_venue_examples_text("value_agent.j2", default_profile)
    hardcore_text = build_venue_examples_text("value_agent.j2", hardcore_profile)
    abstract_text = build_venue_examples_text("value_agent.j2", abstract_profile)

    assert "balanced default SHIT desk standard" in default_text
    assert "hardcore SHIT lane" in hardcore_text
    assert "abstract SHIT lane" in abstract_text
    assert "High venue fit" in default_text


def test_venue_guidance_mentions_legal_boundary() -> None:
    guidance = build_venue_guidance_text(VenueProfile.default_screening_profile())

    assert "academic camouflage" in guidance
    assert "revenge porn" in guidance
    assert "actionable crime instructions" in guidance
