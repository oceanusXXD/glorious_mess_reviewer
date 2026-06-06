"""Schema validation tests."""

import json
import pytest
from pydantic import ValidationError

from glorious_mess_reviewer.schemas import (
    EvidenceItem,
    EvidenceAgentOutput,
    FinalMetaReviewOutput,
    ManuscriptInput,
    RawAgentOutputEnvelope,
    ValueAgentOutput,
    VenueProfile,
)


def test_manuscript_requires_identifier() -> None:
    with pytest.raises(ValidationError):
        ManuscriptInput.model_validate({"title": "x", "abstract": "y", "body": "z"})


def test_manuscript_rejects_blank_identifier_after_trimming() -> None:
    with pytest.raises(ValidationError):
        ManuscriptInput.model_validate({"manuscript_id": "   ", "title": "x", "abstract": "y", "body": "z"})


def test_manuscript_trims_identifier_for_storage_and_queries() -> None:
    manuscript = ManuscriptInput.model_validate(
        {"manuscript_id": "  m-1  ", "title": "x", "abstract": "y", "body": "z"}
    )

    assert manuscript.manuscript_id == "m-1"


def test_default_venue_has_all_weights() -> None:
    venue = VenueProfile.default_screening_profile()
    assert len(venue.scoring_weights) == 12


def test_invalid_venue_weights_are_rejected() -> None:
    venue = VenueProfile.default_screening_profile().model_dump(mode="json")
    venue["scoring_weights"].pop("overall_merit")
    with pytest.raises(ValidationError):
        VenueProfile.model_validate(venue)


def test_venue_can_override_minimum_reviewable_characters() -> None:
    venue = VenueProfile.default_screening_profile()
    venue.minimum_reviewable_characters = 321
    assert venue.minimum_reviewable_characters == 321


def test_manuscript_rejects_unknown_top_level_fields() -> None:
    with pytest.raises(ValidationError):
        ManuscriptInput.model_validate(
            {
                "manuscript_id": "m-1",
                "title": "x",
                "abstract": "y",
                "body": "z",
                "unexpected": True,
            }
        )


def test_venue_recommendation_policy_rejects_unknown_keys() -> None:
    venue = VenueProfile.default_screening_profile().model_dump(mode="json")
    venue["recommendation_policy"]["mystery_threshold"] = 123
    with pytest.raises(ValidationError):
        VenueProfile.model_validate(venue)


def test_venue_recommendation_policy_rejects_ascending_thresholds() -> None:
    venue = VenueProfile.default_screening_profile().model_dump(mode="json")
    venue["recommendation_policy"]["advance_to_full_review_min_final_score"] = 3.0
    venue["recommendation_policy"]["advance_with_payload_reservations_min_final_score"] = 3.7

    with pytest.raises(ValidationError):
        VenueProfile.model_validate(venue)


def test_venue_rejects_all_zero_scoring_weights() -> None:
    venue = VenueProfile.default_screening_profile().model_dump(mode="json")
    venue["scoring_weights"] = {key: 0 for key in venue["scoring_weights"]}
    with pytest.raises(ValidationError):
        VenueProfile.model_validate(venue)


def test_provider_facing_response_models_avoid_property_names_in_json_schema() -> None:
    for model in (EvidenceAgentOutput, ValueAgentOutput, FinalMetaReviewOutput):
        schema_json = json.dumps(model.model_json_schema())
        assert "propertyNames" not in schema_json


def test_evidence_item_accepts_legacy_string_values() -> None:
    item = EvidenceItem.model_validate("quoted text")

    assert item.excerpt == "quoted text"
    assert item.source_type.value == "manuscript"


def test_raw_agent_output_envelope_accepts_typed_payloads() -> None:
    envelope = RawAgentOutputEnvelope.model_validate(
        {
            "status": "success",
            "artifact_type": "precheck_output",
            "payload": {
                "decision": "pass",
                "minimum_reviewable": True,
                "hard_failures": [],
                "missing_sections": [],
                "risk_flags": [],
                "notes": [],
            },
        }
    )

    assert envelope.artifact_type is not None
    assert envelope.artifact_type.value == "precheck_output"
