"""Scoring and recommendation rule tests."""

from glorious_mess_reviewer.schemas import (
    PrecheckDecision,
    PrecheckOutput,
    ReviewDimension,
    ReviewDimensionScore,
    VenuePresetName,
    VenueProfile,
)
from glorious_mess_reviewer.scoring import (
    apply_post_review_rules,
    compute_screening_recommendation,
    compute_weighted_confidence,
    compute_weighted_final_score,
    find_low_confidence_advancement_dimensions,
)


def _score(value: int, reason: str = "ok", *, confidence: float = 0.9) -> ReviewDimensionScore:
    return ReviewDimensionScore(
        score=value,
        confidence=confidence,
        reason=reason,
        supporting_evidence=["evidence"],
        uncertainty_note=None,
    )


def test_weighted_score_stays_in_range() -> None:
    venue = VenueProfile.default_screening_profile()
    scores = {dimension: _score(4) for dimension in ReviewDimension}
    assert compute_weighted_final_score(scores, venue) == 4.0


def test_weighted_confidence_uses_venue_weights() -> None:
    venue = VenueProfile.default_screening_profile()
    scores = {dimension: _score(4, confidence=0.8) for dimension in ReviewDimension}
    scores[ReviewDimension.overall_merit] = _score(4, confidence=0.4)

    confidence = compute_weighted_confidence(scores, venue)

    assert confidence == 0.76


def test_gimmick_without_payload_gets_rejected() -> None:
    venue = VenueProfile.default_screening_profile()
    scores = {dimension: _score(3) for dimension in ReviewDimension}
    scores[ReviewDimension.zhenghuo_execution] = _score(5)
    scores[ReviewDimension.result_payload] = _score(1)
    precheck = PrecheckOutput(decision=PrecheckDecision.PASS, minimum_reviewable=True)
    recommendation, _ = compute_screening_recommendation(
        precheck=precheck,
        scores_by_dimension=scores,
        venue_profile=venue,
        final_score=3.2,
    )
    assert recommendation.value == "REJECT_AS_EMPTY_GIMMICK"


def test_missing_claim_caps_overall() -> None:
    venue = VenueProfile.default_screening_profile()
    scores = {dimension: _score(4) for dimension in ReviewDimension}
    scores[ReviewDimension.core_claim_clarity] = _score(1)
    precheck = PrecheckOutput(decision=PrecheckDecision.PASS, minimum_reviewable=True)
    updated, rule_hits, _ = apply_post_review_rules(
        precheck=precheck,
        scores_by_dimension=scores,
        venue_profile=venue,
        meta_rationale="initial",
    )
    assert updated[ReviewDimension.overall_merit].score == 2
    assert any(hit.code == "no_core_claim_caps_overall" for hit in rule_hits)


def test_custom_venue_can_disable_gimmick_cap() -> None:
    venue = VenueProfile.default_screening_profile()
    venue.rejection_rules = [
        rule for rule in venue.rejection_rules if rule != "gimmick_without_payload_caps_overall_at_three"
    ]
    scores = {dimension: _score(4) for dimension in ReviewDimension}
    scores[ReviewDimension.zhenghuo_execution] = _score(5)
    scores[ReviewDimension.result_payload] = _score(1)
    updated, rule_hits, _ = apply_post_review_rules(
        precheck=PrecheckOutput(decision=PrecheckDecision.PASS, minimum_reviewable=True),
        scores_by_dimension=scores,
        venue_profile=venue,
        meta_rationale="initial",
    )
    assert updated[ReviewDimension.overall_merit].score == 4
    assert all(hit.code != "gimmick_without_payload_cap" for hit in rule_hits)


def test_gimmick_rule_caps_overall_merit_when_enabled() -> None:
    venue = VenueProfile.default_screening_profile()
    scores = {dimension: _score(4) for dimension in ReviewDimension}
    scores[ReviewDimension.zhenghuo_execution] = _score(5)
    scores[ReviewDimension.result_payload] = _score(1)
    scores[ReviewDimension.overall_merit] = _score(5)

    updated, rule_hits, rationale = apply_post_review_rules(
        precheck=PrecheckOutput(decision=PrecheckDecision.PASS, minimum_reviewable=True),
        scores_by_dimension=scores,
        venue_profile=venue,
        meta_rationale="initial",
    )

    assert updated[ReviewDimension.overall_merit].score == 3
    assert any(hit.code == "gimmick_without_payload_cap" for hit in rule_hits)
    assert "gimmick energy without enough payload" in rationale


def test_risk_flags_force_revision_even_with_high_score() -> None:
    venue = VenueProfile.default_screening_profile()
    scores = {dimension: _score(5) for dimension in ReviewDimension}
    precheck = PrecheckOutput(
        decision=PrecheckDecision.REVISION_REQUIRED,
        minimum_reviewable=True,
        risk_flags=["risk_dangerous_actionable"],
    )
    recommendation, _ = compute_screening_recommendation(
        precheck=precheck,
        scores_by_dimension=scores,
        venue_profile=venue,
        final_score=4.8,
    )
    assert recommendation.value == "ESCALATE_FOR_HUMAN_RISK_CHECK"


def test_hard_failures_do_not_override_risk_escalation() -> None:
    venue = VenueProfile.default_screening_profile()
    scores = {dimension: _score(5) for dimension in ReviewDimension}
    precheck = PrecheckOutput(
        decision=PrecheckDecision.REJECT,
        minimum_reviewable=False,
        hard_failures=["missing_abstract"],
        risk_flags=["risk_dangerous_actionable"],
    )

    recommendation, _ = compute_screening_recommendation(
        precheck=precheck,
        scores_by_dimension=scores,
        venue_profile=venue,
        final_score=4.8,
    )

    assert recommendation.value == "ESCALATE_FOR_HUMAN_RISK_CHECK"


def test_accept_but_needs_more_payload_branch() -> None:
    venue = VenueProfile.default_screening_profile()
    scores = {dimension: _score(4) for dimension in ReviewDimension}
    scores[ReviewDimension.result_payload] = _score(3)
    precheck = PrecheckOutput(decision=PrecheckDecision.PASS, minimum_reviewable=True)

    recommendation, _ = compute_screening_recommendation(
        precheck=precheck,
        scores_by_dimension=scores,
        venue_profile=venue,
        final_score=3.9,
    )

    assert recommendation.value == "ADVANCE_WITH_PAYLOAD_RESERVATIONS"


def test_borderline_but_funny_branch() -> None:
    venue = VenueProfile.default_screening_profile()
    scores = {dimension: _score(3) for dimension in ReviewDimension}
    scores[ReviewDimension.zhenghuo_execution] = _score(4)
    scores[ReviewDimension.venue_fit] = _score(3)
    scores[ReviewDimension.result_payload] = _score(3)
    precheck = PrecheckOutput(decision=PrecheckDecision.PASS, minimum_reviewable=True)

    recommendation, _ = compute_screening_recommendation(
        precheck=precheck,
        scores_by_dimension=scores,
        venue_profile=venue,
        final_score=3.0,
    )

    assert recommendation.value == "BORDERLINE_FOR_FULL_REVIEW"


def test_reject_as_incoherent_sludge_branch() -> None:
    venue = VenueProfile.default_screening_profile()
    scores = {dimension: _score(3) for dimension in ReviewDimension}
    scores[ReviewDimension.core_claim_clarity] = _score(1)
    scores[ReviewDimension.method_or_reasoning_legibility] = _score(2)
    precheck = PrecheckOutput(decision=PrecheckDecision.PASS, minimum_reviewable=True)

    recommendation, _ = compute_screening_recommendation(
        precheck=precheck,
        scores_by_dimension=scores,
        venue_profile=venue,
        final_score=2.6,
    )

    assert recommendation.value == "REJECT_AS_INCOHERENT_SLUDGE"


def test_missing_core_sections_rule_caps_structural_integrity() -> None:
    venue = VenueProfile.default_screening_profile()
    scores = {dimension: _score(4) for dimension in ReviewDimension}
    precheck = PrecheckOutput(
        decision=PrecheckDecision.REVISION_REQUIRED,
        minimum_reviewable=False,
        missing_sections=["abstract"],
    )

    updated, rule_hits, _ = apply_post_review_rules(
        precheck=precheck,
        scores_by_dimension=scores,
        venue_profile=venue,
        meta_rationale="initial",
    )

    assert updated[ReviewDimension.structural_integrity].score == 1
    assert any(hit.code == "missing_core_sections" for hit in rule_hits)


def test_no_evidence_rule_caps_evidence_checkability() -> None:
    venue = VenueProfile.default_screening_profile()
    scores = {dimension: _score(4) for dimension in ReviewDimension}
    scores[ReviewDimension.evidence_checkability] = ReviewDimensionScore(
        score=4,
        confidence=0.9,
        reason="claimed evidence existed",
        supporting_evidence=[],
        uncertainty_note=None,
    )

    updated, rule_hits, _ = apply_post_review_rules(
        precheck=PrecheckOutput(decision=PrecheckDecision.PASS, minimum_reviewable=True),
        scores_by_dimension=scores,
        venue_profile=venue,
        meta_rationale="initial",
    )

    assert updated[ReviewDimension.evidence_checkability].score == 2
    assert any(hit.code == "no_evidence_caps_checkability" for hit in rule_hits)


def test_risk_flags_rule_records_trace_hit() -> None:
    venue = VenueProfile.default_screening_profile()
    scores = {dimension: _score(4) for dimension in ReviewDimension}
    updated, rule_hits, rationale = apply_post_review_rules(
        precheck=PrecheckOutput(
            decision=PrecheckDecision.REVISION_REQUIRED,
            minimum_reviewable=True,
            risk_flags=["risk_dangerous_actionable"],
        ),
        scores_by_dimension=scores,
        venue_profile=venue,
        meta_rationale="initial",
    )

    assert updated[ReviewDimension.overall_merit].score == 4
    assert any(hit.code == "risk_flags_present" for hit in rule_hits)
    assert "Risk flags were raised during precheck" in rationale


def test_low_confidence_advancement_gate_routes_to_human_check() -> None:
    venue = VenueProfile.default_screening_profile()
    scores = {dimension: _score(5) for dimension in ReviewDimension}
    scores[ReviewDimension.result_payload] = _score(5, confidence=0.35)
    scores[ReviewDimension.evidence_checkability] = _score(5, confidence=0.45)

    updated, rule_hits, rationale = apply_post_review_rules(
        precheck=PrecheckOutput(decision=PrecheckDecision.PASS, minimum_reviewable=True),
        scores_by_dimension=scores,
        venue_profile=venue,
        meta_rationale="initial",
    )
    final_score = compute_weighted_final_score(updated, venue)
    recommendation, recommendation_reason = compute_screening_recommendation(
        precheck=PrecheckOutput(decision=PrecheckDecision.PASS, minimum_reviewable=True),
        scores_by_dimension=updated,
        venue_profile=venue,
        final_score=final_score,
    )

    low_confidence_dimensions = find_low_confidence_advancement_dimensions(updated)
    assert [dimension.value for dimension in low_confidence_dimensions] == [
        "evidence_checkability",
        "result_payload",
    ]
    assert any(hit.code == "low_confidence_advancement_gate" for hit in rule_hits)
    assert "Advancement-critical scores have low confidence" in rationale
    assert recommendation.value == "BORDERLINE_FOR_FULL_REVIEW"
    assert "low-confidence advancement-critical dimensions" in recommendation_reason


def test_advance_to_full_review_branch() -> None:
    venue = VenueProfile.default_screening_profile()
    scores = {dimension: _score(4) for dimension in ReviewDimension}
    scores[ReviewDimension.result_payload] = _score(5)
    scores[ReviewDimension.venue_fit] = _score(4)

    recommendation, _ = compute_screening_recommendation(
        precheck=PrecheckOutput(decision=PrecheckDecision.PASS, minimum_reviewable=True),
        scores_by_dimension=scores,
        venue_profile=venue,
        final_score=4.4,
    )

    assert recommendation.value == "ADVANCE_TO_FULL_REVIEW"


def test_builtin_shit_presets_are_available() -> None:
    hardcore = VenueProfile.from_builtin_preset(VenuePresetName.SHIT_HARDCORE_SCREENING)
    abstract = VenueProfile.from_builtin_preset(VenuePresetName.SHIT_ABSTRACT_SCREENING)

    assert hardcore.venue_name == "S.H.I.T Hardcore Screening Track"
    assert abstract.venue_name == "S.H.I.T Abstract Screening Track"
    assert hardcore.minimum_reviewable_characters is not None
    assert abstract.scoring_weights[ReviewDimension.zhenghuo_execution] > hardcore.scoring_weights[ReviewDimension.zhenghuo_execution]
