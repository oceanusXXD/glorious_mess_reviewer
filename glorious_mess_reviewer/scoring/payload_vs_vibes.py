"""Deterministic score aggregation and venue-aware recommendation rules."""

from __future__ import annotations

from glorious_mess_reviewer.schemas import (
    AgentFailure,
    EvidenceSourceType,
    EvidenceAgentOutput,
    FinalMetaReviewOutput,
    PrecheckOutput,
    RecommendationLabel,
    ReviewDimension,
    ReviewDimensionScore,
    RuleHit,
    ValueAgentOutput,
    VenueProfile,
    build_all_dimension_scores,
    build_evidence_item,
    build_low_confidence_score,
)

ADVANCEMENT_CONFIDENCE_FLOOR = 0.55
ADVANCEMENT_CONFIDENCE_DIMENSIONS = (
    ReviewDimension.core_claim_clarity,
    ReviewDimension.evidence_checkability,
    ReviewDimension.result_payload,
    ReviewDimension.meme_to_argument_conversion,
    ReviewDimension.overall_merit,
)


def _rule_enabled(venue_profile: VenueProfile, *aliases: str) -> bool:
    """Return whether a venue explicitly enables a named rejection or cap rule."""

    configured = set(venue_profile.rejection_rules)
    return any(alias in configured for alias in aliases)


def merge_sludge_panel_reviews(
    *,
    evidence_output: EvidenceAgentOutput | None,
    value_output: ValueAgentOutput | None,
) -> FinalMetaReviewOutput:
    """Aggregate partial subreviews into a fallback meta review."""

    evidence_scores = evidence_output.dimension_scores.as_dict() if evidence_output else {}
    value_scores = value_output.dimension_scores.as_dict() if value_output else {}
    score_map: dict[ReviewDimension, ReviewDimensionScore] = {}
    for dimension in ReviewDimension:
        candidate = evidence_scores.get(dimension)
        if candidate is None:
            candidate = value_scores.get(dimension)
        score_map[dimension] = candidate or build_low_confidence_score(
            f"{dimension.value} used fallback scoring because meta aggregation was unavailable."
        )

    strengths = []
    weaknesses = []
    required = []
    optional = []
    risk_flags = []
    if evidence_output:
        strengths.extend(evidence_output.major_strengths)
        weaknesses.extend(evidence_output.major_weaknesses)
        required.extend(evidence_output.required_revisions)
        optional.extend(evidence_output.optional_revisions)
        risk_flags.extend(evidence_output.risk_flags)
    if value_output:
        strengths.extend(value_output.major_strengths)
        weaknesses.extend(value_output.major_weaknesses)
        required.extend(value_output.required_revisions)
        optional.extend(value_output.optional_revisions)
        risk_flags.extend(value_output.risk_flags)

    summary = evidence_output.paper_summary if evidence_output else "Summary unavailable because the evidence agent failed."
    claim = (
        evidence_output.extracted_core_claim
        if evidence_output and evidence_output.extracted_core_claim
        else "unknown"
    )
    return FinalMetaReviewOutput(
        paper_summary=summary,
        extracted_core_claim=claim,
        scores_by_dimension=build_all_dimension_scores(score_map),
        major_strengths=_dedupe(strengths),
        major_weaknesses=_dedupe(weaknesses),
        required_revisions=_dedupe(required),
        optional_revisions=_dedupe(optional),
        risk_flags=_dedupe(risk_flags),
        final_rationale="Meta-review agent unavailable; result composed from surviving subagents and deterministic rules.",
        community_facing_blurb="Panel degraded gracefully. The manuscript was judged with partial subagent coverage, so treat this verdict as lower confidence.",
    )


def compute_weighted_final_score(
    scores_by_dimension: dict[ReviewDimension, ReviewDimensionScore],
    venue_profile: VenueProfile,
) -> float:
    """Compute the weighted final score on a 1-5 scale."""

    weighted_total = 0.0
    total_weight = 0.0
    for dimension, weight in venue_profile.scoring_weights.items():
        weighted_total += scores_by_dimension[dimension].score * weight
        total_weight += weight
    return round(weighted_total / total_weight, 2)


def compute_weighted_confidence(
    scores_by_dimension: dict[ReviewDimension, ReviewDimensionScore],
    venue_profile: VenueProfile,
) -> float:
    """Compute the venue-weighted confidence behind a panel verdict."""

    weighted_total = 0.0
    total_weight = 0.0
    for dimension, weight in venue_profile.scoring_weights.items():
        weighted_total += scores_by_dimension[dimension].confidence * weight
        total_weight += weight
    return round(weighted_total / total_weight, 2)


def find_low_confidence_advancement_dimensions(
    scores_by_dimension: dict[ReviewDimension, ReviewDimensionScore],
    *,
    floor: float = ADVANCEMENT_CONFIDENCE_FLOOR,
) -> list[ReviewDimension]:
    """Return high-scoring advancement dimensions whose confidence is too low."""

    return [
        dimension
        for dimension in ADVANCEMENT_CONFIDENCE_DIMENSIONS
        if scores_by_dimension[dimension].score >= 4 and scores_by_dimension[dimension].confidence < floor
    ]


def apply_post_review_rules(
    *,
    precheck: PrecheckOutput,
    scores_by_dimension: dict[ReviewDimension, ReviewDimensionScore],
    venue_profile: VenueProfile,
    meta_rationale: str,
) -> tuple[dict[ReviewDimension, ReviewDimensionScore], list[RuleHit], str]:
    """Apply configurable hard caps and trace which rules changed the result."""

    updated = dict(scores_by_dimension)
    rule_hits: list[RuleHit] = []
    rationale_notes = [meta_rationale]

    # 规则顺序本身就是业务策略：先收紧硬结构，再处理 claim、evidence、gimmick 等软约束，避免后面的分支掩盖前面的硬问题。
    missing_core_sections = {"title", "abstract", "body"}.intersection(precheck.missing_sections)
    if missing_core_sections and _rule_enabled(
        venue_profile,
        "missing_title_or_abstract_or_body_is_hard_failure",
        "missing_core_sections",
    ):
        rule_hits.append(
            RuleHit(
                code="missing_core_sections",
                description="Core manuscript sections are missing, so full review quality is capped.",
                effect=f"hard failure: {sorted(missing_core_sections)}",
            )
        )
        updated[ReviewDimension.structural_integrity] = ReviewDimensionScore(
            score=1,
            confidence=1.0,
            reason="Core required sections are missing, which prevents a structurally complete review.",
            supporting_evidence=[
                build_evidence_item(
                    f"Missing sections: {', '.join(sorted(missing_core_sections))}",
                    source_type=EvidenceSourceType.rule,
                )
            ],
            uncertainty_note=None,
        )
        rationale_notes.append("Core sections are missing, so the manuscript cannot earn a structurally healthy verdict.")

    if updated[ReviewDimension.core_claim_clarity].score <= 1 and _rule_enabled(
        venue_profile,
        "no_core_claim_caps_overall_at_two",
        "no_core_claim_caps_overall",
    ):
        rule_hits.append(
            RuleHit(
                code="no_core_claim_caps_overall",
                description="Without a recognizable core claim, overall merit cannot exceed 2.",
                effect="overall_merit capped at 2",
            )
        )
        updated[ReviewDimension.overall_merit] = _cap_score(
            updated[ReviewDimension.overall_merit],
            2,
            "No identifiable core claim, so overall merit is capped by rule.",
        )
        rationale_notes.append("No identifiable core claim was found, which caps overall merit.")

    if (
        updated[ReviewDimension.evidence_checkability].score > 2
        and not _has_supporting_evidence(updated[ReviewDimension.evidence_checkability])
        and _rule_enabled(
            venue_profile,
            "no_checkable_evidence_caps_evidence_at_two",
            "no_evidence_caps_checkability",
        )
    ):
        rule_hits.append(
            RuleHit(
                code="no_evidence_caps_checkability",
                description="Evidence checkability cannot exceed 2 without any cited evidence.",
                effect="evidence_checkability capped at 2",
            )
        )
        updated[ReviewDimension.evidence_checkability] = _cap_score(
            updated[ReviewDimension.evidence_checkability],
            2,
            "Evidence score capped because no supporting evidence snippets were provided.",
        )
        rationale_notes.append("Evidence checkability was capped because the review panel had no checkable snippets.")

    if (
        updated[ReviewDimension.zhenghuo_execution].score >= 4
        and updated[ReviewDimension.result_payload].score <= 2
        and updated[ReviewDimension.overall_merit].score > 3
        and _rule_enabled(
            venue_profile,
            "gimmick_without_payload_caps_overall_at_three",
            "gimmick_without_payload_cap",
        )
    ):
        rule_hits.append(
            RuleHit(
                code="gimmick_without_payload_cap",
                description="Strong zhenghuo without payload cannot yield a high overall score.",
                effect="overall_merit capped at 3",
            )
        )
        updated[ReviewDimension.overall_merit] = _cap_score(
            updated[ReviewDimension.overall_merit],
            3,
            "The manuscript has surface-level zhenghuo energy but insufficient payload.",
        )
        rationale_notes.append("The work shows gimmick energy without enough payload, so overall merit is capped.")

    if precheck.risk_flags and _rule_enabled(
        venue_profile,
        "unsafe_or_abusive_content_sets_risk_flag",
        "risk_flags_present",
    ):
        rule_hits.append(
            RuleHit(
                code="risk_flags_present",
                description="Potentially unsafe or abusive content requires extra caution.",
                effect="recommendation will be conservative",
            )
        )
        rationale_notes.append("Risk flags were raised during precheck, so the system keeps the recommendation conservative.")

    low_confidence_dimensions = find_low_confidence_advancement_dimensions(updated)
    if low_confidence_dimensions and _rule_enabled(
        venue_profile,
        "low_confidence_advancement_gate",
        "low_confidence_core_scores_require_human_check",
    ):
        formatted_dimensions = ", ".join(dimension.value for dimension in low_confidence_dimensions)
        rule_hits.append(
            RuleHit(
                code="low_confidence_advancement_gate",
                description="High advancement-critical scores need enough confidence before automatic advancement.",
                effect=f"full-review advancement gated for low confidence: {formatted_dimensions}",
            )
        )
        rationale_notes.append(
            "Advancement-critical scores have low confidence "
            f"({formatted_dimensions}), so any positive decision should stay in a human-check lane."
        )

    return updated, rule_hits, " ".join(rationale_notes).strip()


def compute_screening_recommendation(
    *,
    precheck: PrecheckOutput,
    scores_by_dimension: dict[ReviewDimension, ReviewDimensionScore],
    venue_profile: VenueProfile,
    final_score: float,
) -> tuple[RecommendationLabel, str]:
    """Convert scores and hard rules into an initial-screening decision."""

    # recommendation 不是简单按总分排序，先处理 hard failure 与高风险分支，再落到 venue policy 阈值。
    overall = scores_by_dimension[ReviewDimension.overall_merit].score
    venue_fit = scores_by_dimension[ReviewDimension.venue_fit].score
    payload = scores_by_dimension[ReviewDimension.result_payload].score
    clarity = scores_by_dimension[ReviewDimension.core_claim_clarity].score
    zhenghuo = scores_by_dimension[ReviewDimension.zhenghuo_execution].score
    reasoning = scores_by_dimension[ReviewDimension.method_or_reasoning_legibility].score

    if precheck.risk_flags:
        return (
            RecommendationLabel.ESCALATE_FOR_HUMAN_RISK_CHECK,
            "Risk flags require human moderation before the manuscript can be cleared for the next review stage.",
        )

    if precheck.hard_failures:
        return (
            RecommendationLabel.REVISION_REQUIRED_BEFORE_REVIEW,
            "Precheck found hard failures that must be repaired before the manuscript can enter full review.",
        )

    if zhenghuo >= 4 and payload <= 2:
        return (
            RecommendationLabel.REJECT_AS_EMPTY_GIMMICK,
            "The manuscript has visible gimmick energy but too little payload to justify advancing beyond screening.",
        )

    if clarity <= 1 and reasoning <= 2:
        return (
            RecommendationLabel.REJECT_AS_INCOHERENT_SLUDGE,
            "The manuscript does not present a coherent core claim or traceable reasoning.",
        )

    policy = venue_profile.recommendation_policy
    low_confidence_dimensions = find_low_confidence_advancement_dimensions(scores_by_dimension)
    if (
        low_confidence_dimensions
        and final_score >= policy.advance_with_payload_reservations_min_final_score
        and _rule_enabled(
            venue_profile,
            "low_confidence_advancement_gate",
            "low_confidence_core_scores_require_human_check",
        )
    ):
        formatted_dimensions = ", ".join(dimension.value for dimension in low_confidence_dimensions)
        if venue_fit >= policy.venue_fit_floor_for_advance and zhenghuo >= 3:
            return (
                RecommendationLabel.BORDERLINE_FOR_FULL_REVIEW,
                "The manuscript has strong scoring signals, but low-confidence advancement-critical dimensions "
                f"({formatted_dimensions}) should be checked by a human before full-review advancement.",
            )
        return (
            RecommendationLabel.REVISION_REQUIRED_BEFORE_REVIEW,
            "The manuscript has high scoring signals in places, but low-confidence advancement-critical dimensions "
            f"({formatted_dimensions}) need clearer evidence before it should advance.",
        )

    # 到这里才进入分数阈值分流；如果把 policy 分支提前，会让前面的风险/空心 gimmick 保护失效。
    if (
        final_score >= policy.advance_to_full_review_min_final_score
        and payload >= max(4, policy.payload_floor_for_advance)
        and venue_fit >= policy.venue_fit_floor_for_advance
    ):
        return (
            RecommendationLabel.ADVANCE_TO_FULL_REVIEW,
            "The manuscript clears initial screening with enough payload and venue-aware execution to move into full review.",
        )

    if (
        final_score >= policy.advance_with_payload_reservations_min_final_score
        and payload >= policy.payload_floor_for_advance
        and venue_fit >= policy.venue_fit_floor_for_advance
    ):
        return (
            RecommendationLabel.ADVANCE_WITH_PAYLOAD_RESERVATIONS,
            "The manuscript should advance, but the next review stage should keep an eye on payload density.",
        )

    if final_score >= policy.borderline_for_full_review_min_final_score and zhenghuo >= 4 and venue_fit >= 3:
        return (
            RecommendationLabel.BORDERLINE_FOR_FULL_REVIEW,
            "The work is borderline, but there is enough venue-aware value to justify a closer human look.",
        )

    if venue_fit <= 2 and reasoning >= 4:
        return (
            RecommendationLabel.REVISION_REQUIRED_BEFORE_REVIEW,
            "The reasoning is respectable, but the manuscript currently reads like a serious paper in the wrong room for this screening track.",
        )

    if overall <= 2 or final_score < 2.5:
        return (
            RecommendationLabel.REJECT_AS_INCOHERENT_SLUDGE,
            "The combined score indicates substantial coherence or quality failures.",
        )

    if payload <= 2:
        return (
            RecommendationLabel.REJECT_AS_EMPTY_GIMMICK,
            "The manuscript does not deliver enough substantive payload for this venue.",
        )

    return (
        RecommendationLabel.REVISION_REQUIRED_BEFORE_REVIEW,
        "The manuscript shows promise but needs revision before it should be sent onward from initial screening.",
    )


def compute_glorious_mess_recommendation(
    *,
    precheck: PrecheckOutput,
    scores_by_dimension: dict[ReviewDimension, ReviewDimensionScore],
    venue_profile: VenueProfile,
    final_score: float,
) -> tuple[RecommendationLabel, str]:
    """Backward-compatible alias for screening recommendation logic."""

    return compute_screening_recommendation(
        precheck=precheck,
        scores_by_dimension=scores_by_dimension,
        venue_profile=venue_profile,
        final_score=final_score,
    )


def _cap_score(score: ReviewDimensionScore, maximum: int, reason: str) -> ReviewDimensionScore:
    return ReviewDimensionScore(
        score=min(score.score, maximum),
        confidence=max(score.confidence, 0.8),
        reason=reason,
        supporting_evidence=score.supporting_evidence,
        uncertainty_note=score.uncertainty_note,
    )


def _has_supporting_evidence(score: ReviewDimensionScore) -> bool:
    return any(item.excerpt.strip() for item in score.supporting_evidence)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        normalized = item.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return deduped
