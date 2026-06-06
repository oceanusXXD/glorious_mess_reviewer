"""Prompt rendering tests."""

from glorious_mess_reviewer.prompts import render_prompt
from glorious_mess_reviewer.prompts.venue_guidance import build_venue_guidance_text
from glorious_mess_reviewer.schemas import ManuscriptInput, VenueProfile


def test_precheck_prompt_renders_manuscript_and_venue() -> None:
    manuscript = ManuscriptInput(
        manuscript_id="m1",
        title="Title",
        abstract="Abstract",
        body="Body",
    )
    prompt = render_prompt(
        "precheck_agent.j2",
        manuscript=manuscript,
        venue_profile_json=VenueProfile.default_screening_profile().model_dump_json(),
        venue_guidance_text=build_venue_guidance_text(VenueProfile.default_screening_profile()),
        venue_examples_text="Calibration examples",
        minimum_reviewable_characters=200,
    )
    assert "HanCeGateAgent" in prompt.content
    assert "Title" in prompt.content
    assert "minimum reviewable characters" in prompt.content.lower()
    assert "initial screening" in prompt.content.lower()
    assert "Calibration examples" in prompt.content


def test_value_prompt_contains_funny_but_empty_guardrail() -> None:
    manuscript = ManuscriptInput(
        manuscript_id="m2",
        title="Title",
        abstract="Abstract",
        body="Body",
    )
    prompt = render_prompt(
        "value_agent.j2",
        manuscript=manuscript,
        venue_profile_json=VenueProfile.default_screening_profile().model_dump_json(),
        venue_guidance_text=build_venue_guidance_text(VenueProfile.default_screening_profile()),
        venue_examples_text="High venue fit",
    )
    assert "funny but empty" in prompt.content
    assert "community reviewers would actually upvote" in prompt.content
    assert "academic cosplay" in prompt.content
    assert "High venue fit" in prompt.content


def test_evidence_prompt_mentions_argument_and_evidence_distinction() -> None:
    manuscript = ManuscriptInput(
        manuscript_id="m3",
        title="Title",
        abstract="Abstract",
        body="Body",
    )
    prompt = render_prompt(
        "evidence_agent.j2",
        manuscript=manuscript,
        venue_profile_json=VenueProfile.default_screening_profile().model_dump_json(),
        venue_guidance_text=build_venue_guidance_text(VenueProfile.default_screening_profile()),
        venue_examples_text="Absurd but substantive",
    )
    assert "evidence insufficient" in prompt.content
    assert "logic broken" in prompt.content
    assert "academic camouflage" in prompt.content
    assert "revenge porn" in prompt.content
    assert "Absurd but substantive" in prompt.content


def test_meta_prompt_includes_upstream_review_context() -> None:
    manuscript = ManuscriptInput(
        manuscript_id="m4",
        title="Title",
        abstract="Abstract",
        body="Body",
    )
    prompt = render_prompt(
        "meta_agent.j2",
        manuscript=manuscript,
        venue_profile_json=VenueProfile.default_screening_profile().model_dump_json(),
        venue_guidance_text=build_venue_guidance_text(VenueProfile.default_screening_profile()),
        venue_examples_text="If evidence says",
        precheck_json="{}",
        evidence_json="{}",
        value_json="{}",
    )
    assert "Precheck output" in prompt.content
    assert "Evidence review" in prompt.content
    assert "Zhenghuo review" in prompt.content
    assert "screening recommendation" in prompt.content.lower()
    assert "thesis-bearing zhenghuo" in prompt.content
    assert "If evidence says" in prompt.content


def test_precheck_prompt_mentions_illegal_or_abusive_boundary() -> None:
    manuscript = ManuscriptInput(
        manuscript_id="m5",
        title="Title",
        abstract="Abstract",
        body="Body",
    )
    prompt = render_prompt(
        "precheck_agent.j2",
        manuscript=manuscript,
        venue_profile_json=VenueProfile.default_screening_profile().model_dump_json(),
        venue_guidance_text=build_venue_guidance_text(VenueProfile.default_screening_profile()),
        venue_examples_text="Calibration examples",
        minimum_reviewable_characters=200,
    )
    assert "SHIT-style play is allowed" in prompt.content
    assert "revenge porn" in prompt.content
