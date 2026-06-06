"""Display projections for persisted review outputs."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from glorious_mess_reviewer.scoring import compute_weighted_confidence, find_low_confidence_advancement_dimensions
from glorious_mess_reviewer.schemas import (
    EvidenceItem,
    ManuscriptInput,
    PersistedReviewRecord,
    RecommendationLabel,
    ReviewDimension,
    ReviewDimensionScore,
    ReviewDisplayGate,
    ReviewDisplayOutput,
    ReviewDisplayQueueOverview,
    ReviewDisplayRepairHotspot,
    ReviewDisplayRepairTarget,
    ReviewDisplayScoreGroup,
    ReviewDisplayScoreRow,
    ReviewDisplaySummary,
    ReviewDisplayTriage,
    ReviewOutput,
    VenueProfile,
)

SHIT_SIGNAL_PANELS: tuple[tuple[str, str, tuple[ReviewDimension, ...]], ...] = (
    (
        "structure_and_evidence",
        "Structure and Evidence",
        (
            ReviewDimension.core_claim_clarity,
            ReviewDimension.structural_integrity,
            ReviewDimension.method_or_reasoning_legibility,
            ReviewDimension.evidence_checkability,
            ReviewDimension.result_payload,
            ReviewDimension.limitation_honesty,
        ),
    ),
    (
        "zhenghuo_conversion",
        "Zhenghuo to Argument",
        (
            ReviewDimension.venue_fit,
            ReviewDimension.zhenghuo_execution,
            ReviewDimension.absurd_originality,
            ReviewDimension.meme_to_argument_conversion,
        ),
    ),
    (
        "community_signal",
        "Community Signal",
        (
            ReviewDimension.community_discussion_value,
            ReviewDimension.overall_merit,
        ),
    ),
)
FERMENTATION_QUEUE_LANES = (
    "human_risk_review",
    "blocked_before_review",
    "degraded_review",
    "human_confidence_check",
    "submission_readiness",
    "author_revision",
    "editor_watch",
    "ready_for_next_stage",
)
FERMENTATION_QUEUE_SORT_KEYS = ("created_at", "queue_priority", "repair_priority")
NON_REPAIR_HOTSPOT_LANES = {"human_risk_review", "blocked_before_review", "degraded_review"}

# Backward-compatible import names for earlier display integrations.
SCORE_GROUPS = SHIT_SIGNAL_PANELS
DISPLAY_SUMMARY_LANES = FERMENTATION_QUEUE_LANES
DISPLAY_SUMMARY_SORT_KEYS = FERMENTATION_QUEUE_SORT_KEYS


def build_review_display(record: PersistedReviewRecord) -> ReviewDisplayOutput:
    """Project a persisted review into a compact dashboard payload."""

    review = record.review
    score_map = review.scores_by_dimension.as_dict()
    low_confidence_dimensions = find_low_confidence_advancement_dimensions(score_map)
    weighted_confidence = compute_weighted_confidence(score_map, review.resolved_venue_profile)
    preset = review.resolved_venue_profile.preset_name
    gates = _display_gates(record)
    signal_panels = _shit_signal_panels(score_map)

    return ReviewDisplayOutput(
        run_id=record.run_id,
        workflow_session_id=review.workflow_session_id,
        manuscript_id=review.manuscript_id,
        recommendation=review.final_recommendation,
        final_score=review.final_score,
        weighted_confidence=weighted_confidence,
        calibration_status=review_confidence_status(weighted_confidence, low_confidence_dimensions),
        suggested_stage=project_review_stage(review.final_recommendation),
        venue_name=review.resolved_venue_profile.venue_name,
        venue_preset=preset.value if preset else None,
        summary=review.paper_summary,
        core_claim=review.extracted_core_claim,
        community_blurb=review.community_facing_blurb,
        triage=_fermentation_queue_triage(review, gates, signal_panels, low_confidence_dimensions),
        gates=gates,
        low_confidence_dimensions=low_confidence_dimensions,
        score_matrix=[
            ReviewDisplayScoreRow(
                dimension=dimension,
                score=score_map[dimension].score,
                confidence=score_map[dimension].confidence,
                evidence=_evidence_strings(score_map[dimension].supporting_evidence),
            )
            for dimension in ReviewDimension
        ],
        score_groups=signal_panels,
        repair_targets=_payload_repair_targets(score_map, review.resolved_venue_profile),
        required_revisions=review.required_revisions,
        optional_revisions=review.optional_revisions,
        strengths=review.major_strengths,
        weaknesses=review.major_weaknesses,
        rule_hits=[hit.code for hit in review.rule_hits],
        created_at=review.created_at,
    )


def build_review_display_summary(record: PersistedReviewRecord) -> ReviewDisplaySummary:
    """Project a persisted review into one queue-list row."""

    display = build_review_display(record)
    return ReviewDisplaySummary(
        run_id=display.run_id,
        manuscript_id=display.manuscript_id,
        created_at=display.created_at,
        recommendation=display.recommendation,
        final_score=display.final_score,
        weighted_confidence=display.weighted_confidence,
        calibration_status=display.calibration_status,
        suggested_stage=display.suggested_stage,
        venue_name=display.venue_name,
        venue_preset=display.venue_preset,
        triage=display.triage,
        top_repair_target=display.repair_targets[0] if display.repair_targets else None,
        needs_review_gates=[gate.name for gate in display.gates if gate.status == "needs_review"],
    )


def build_fermentation_queue_summaries(
    records: Iterable[PersistedReviewRecord],
    *,
    lane: str | None = None,
    sort: str = "created_at",
    limit: int | None = None,
) -> list[ReviewDisplaySummary]:
    """Project persisted reviews into S.H.I.T queue cards with optional queue ordering."""

    queue_cards = [build_review_display_summary(record) for record in records]
    if lane is not None:
        queue_cards = [card for card in queue_cards if card.triage.lane == lane]

    if sort == "queue_priority":
        queue_cards.sort(key=lambda card: (card.triage.queue_priority, card.created_at), reverse=True)
    elif sort == "repair_priority":
        queue_cards.sort(key=_repair_priority_sort_key, reverse=True)
    else:
        queue_cards.sort(key=lambda card: card.created_at, reverse=True)

    if limit is not None:
        return queue_cards[:limit]
    return queue_cards


def build_review_display_summaries(
    records: Iterable[PersistedReviewRecord],
    *,
    lane: str | None = None,
    sort: str = "created_at",
    limit: int | None = None,
) -> list[ReviewDisplaySummary]:
    """Backward-compatible wrapper for fermentation queue summaries."""

    return build_fermentation_queue_summaries(records, lane=lane, sort=sort, limit=limit)


def build_fermentation_queue_overview(records: Iterable[PersistedReviewRecord]) -> ReviewDisplayQueueOverview:
    """Aggregate recent queue cards into dashboard counters and repair hotspots."""

    queue_cards = build_fermentation_queue_summaries(records, sort="created_at")
    lane_counts = {lane: 0 for lane in FERMENTATION_QUEUE_LANES}
    gate_counts: dict[str, int] = {}
    repair_priority_by_dimension: dict[ReviewDimension, list[float]] = {}

    for card in queue_cards:
        lane_counts[card.triage.lane] = lane_counts.get(card.triage.lane, 0) + 1
        for gate_name in card.needs_review_gates:
            gate_counts[gate_name] = gate_counts.get(gate_name, 0) + 1
        if card.top_repair_target is not None and card.triage.lane not in NON_REPAIR_HOTSPOT_LANES:
            repair_priority_by_dimension.setdefault(card.top_repair_target.dimension, []).append(
                card.top_repair_target.priority_score
            )

    return ReviewDisplayQueueOverview(
        total_reviews=len(queue_cards),
        lane_counts=lane_counts,
        gate_counts=dict(sorted(gate_counts.items())),
        needs_human_review=sum(
            lane_counts[lane]
            for lane in ("human_risk_review", "blocked_before_review", "degraded_review", "human_confidence_check")
        ),
        ready_for_next_stage=lane_counts["ready_for_next_stage"],
        average_final_score=_mean_or_none(card.final_score for card in queue_cards),
        average_weighted_confidence=_mean_or_none(card.weighted_confidence for card in queue_cards),
        top_repair_hotspots=_top_repair_hotspots(repair_priority_by_dimension),
    )


def _repair_priority_sort_key(card: ReviewDisplaySummary) -> tuple[float, int, datetime]:
    repair_priority = card.top_repair_target.priority_score if card.top_repair_target else 0.0
    return repair_priority, card.triage.queue_priority, card.created_at


def _mean_or_none(values: Iterable[float]) -> float | None:
    items = list(values)
    if not items:
        return None
    return round(sum(items) / len(items), 2)


def _top_repair_hotspots(
    repair_priority_by_dimension: dict[ReviewDimension, list[float]],
    *,
    limit: int = 5,
) -> list[ReviewDisplayRepairHotspot]:
    hotspots = [
        ReviewDisplayRepairHotspot(
            dimension=dimension,
            count=len(priority_scores),
            max_priority_score=round(max(priority_scores), 2),
            average_priority_score=round(sum(priority_scores) / len(priority_scores), 2),
        )
        for dimension, priority_scores in repair_priority_by_dimension.items()
        if priority_scores
    ]
    return sorted(
        hotspots,
        key=lambda hotspot: (-hotspot.max_priority_score, -hotspot.count, hotspot.dimension.value),
    )[:limit]


def project_review_stage(recommendation: RecommendationLabel) -> str:
    """Map a recommendation into the S.H.I.T-facing review stage ladder."""

    if recommendation == RecommendationLabel.ESCALATE_FOR_HUMAN_RISK_CHECK:
        return "human_risk_review"
    if recommendation in {
        RecommendationLabel.REJECT_AS_EMPTY_GIMMICK,
        RecommendationLabel.REJECT_AS_INCOHERENT_SLUDGE,
        RecommendationLabel.REVISION_REQUIRED_BEFORE_REVIEW,
    }:
        return "petri_dish_revision"
    if recommendation in {
        RecommendationLabel.BORDERLINE_FOR_FULL_REVIEW,
        RecommendationLabel.ADVANCE_WITH_PAYLOAD_RESERVATIONS,
    }:
        return "fermentation"
    return "real_shit_candidate"


def review_confidence_status(
    weighted_confidence: float,
    low_confidence_dimensions: list[ReviewDimension],
) -> str:
    """Return the display status for confidence calibration."""

    if low_confidence_dimensions:
        return "human_check_recommended"
    if weighted_confidence < 0.55:
        return "low_confidence"
    if weighted_confidence < 0.75:
        return "medium_confidence"
    return "high_confidence"


def _display_gates(record: PersistedReviewRecord) -> list[ReviewDisplayGate]:
    review = record.review
    return [
        ReviewDisplayGate(
            name="risk_flags",
            status="pass" if not review.risk_flags else "needs_review",
            detail=_list_detail(review.risk_flags),
        ),
        ReviewDisplayGate(
            name="hard_failures",
            status="pass" if not review.hard_failures else "needs_review",
            detail=_list_detail(review.hard_failures),
        ),
        *_submission_readiness_gates(record.request_payload, review),
        ReviewDisplayGate(
            name="agent_failures",
            status="pass" if not review.agent_failures else "needs_review",
            detail=_list_detail(f"{failure.agent_name}: {failure.error_type}" for failure in review.agent_failures),
        ),
        ReviewDisplayGate(
            name="rule_trace",
            status="info",
            detail=f"{len(review.rule_hits)} rule hit(s)",
        ),
    ]


def _submission_readiness_gates(manuscript: ManuscriptInput, review: ReviewOutput) -> list[ReviewDisplayGate]:
    missing_format = _missing_format_items(manuscript, review)
    references = [item.strip() for item in manuscript.references or [] if item.strip()]
    ai_statement = _metadata_text(manuscript, "ai_use_statement")
    safety_notice = _metadata_text(manuscript, "safety_notice")

    return [
        ReviewDisplayGate(
            name="format_compliance",
            status="pass" if not missing_format else "needs_review",
            detail=(
                "title, abstract, body, and venue-required sections present"
                if not missing_format
                else f"missing: {', '.join(missing_format)}"
            ),
        ),
        ReviewDisplayGate(
            name="citation_traceability",
            status="pass" if references else "needs_review",
            detail=f"{len(references)} reference(s) supplied" if references else "references missing or empty",
        ),
        ReviewDisplayGate(
            name="ai_disclosure_integrity",
            status="pass" if ai_statement else "needs_review",
            detail="metadata.ai_use_statement present" if ai_statement else "metadata.ai_use_statement missing",
        ),
        ReviewDisplayGate(
            name="safety_notice_presence",
            status="pass" if safety_notice else "needs_review",
            detail="metadata.safety_notice present" if safety_notice else "metadata.safety_notice missing",
        ),
    ]


def _shit_signal_panels(
    score_map: dict[ReviewDimension, ReviewDimensionScore],
) -> list[ReviewDisplayScoreGroup]:
    panels: list[ReviewDisplayScoreGroup] = []
    for group_id, label, dimensions in SHIT_SIGNAL_PANELS:
        scores = [score_map[dimension].score for dimension in dimensions]
        confidences = [score_map[dimension].confidence for dimension in dimensions]
        mean_score = round(sum(scores) / len(scores), 2)
        mean_confidence = round(sum(confidences) / len(confidences), 2)
        status = _signal_panel_status(mean_score, mean_confidence)
        weakest_dimension = min(
            dimensions,
            key=lambda dimension: (score_map[dimension].score, score_map[dimension].confidence),
        )
        panels.append(
            ReviewDisplayScoreGroup(
                group_id=group_id,
                label=label,
                dimensions=list(dimensions),
                mean_score=mean_score,
                mean_confidence=mean_confidence,
                status=status,
                weakest_dimension=weakest_dimension,
                weakest_score=score_map[weakest_dimension].score,
                recommended_action=_signal_panel_next_move(group_id, status, weakest_dimension),
            )
        )
    return panels


def _signal_panel_status(mean_score: float, mean_confidence: float) -> str:
    if mean_score >= 4.0 and mean_confidence >= 0.75:
        return "strong"
    if mean_score < 2.5 or mean_confidence < 0.55:
        return "weak"
    return "watch"


def _signal_panel_next_move(group_id: str, status: str, weakest_dimension: ReviewDimension) -> str:
    if group_id == "structure_and_evidence":
        if status == "strong":
            return "Preserve the current structure and evidence trail."
        if status == "weak":
            return f"Repair {weakest_dimension.value} before asking for deeper review."
        return f"Tighten {weakest_dimension.value} before relying on this group."

    if group_id == "zhenghuo_conversion":
        if status == "strong":
            return "Keep the absurd framing disciplined while preserving payload."
        if status == "weak":
            return f"Turn {weakest_dimension.value} into a clearer argument, not just a bit."
        return f"Sharpen {weakest_dimension.value} so the joke carries an argument."

    if status == "strong":
        return "Use this group as the community-facing display hook."
    if status == "weak":
        return f"Clarify {weakest_dimension.value} before presenting the work to the community."
    return f"Make {weakest_dimension.value} more legible to likely readers."


def _payload_repair_targets(
    score_map: dict[ReviewDimension, ReviewDimensionScore],
    venue_profile: VenueProfile,
    *,
    limit: int = 5,
) -> list[ReviewDisplayRepairTarget]:
    targets: list[ReviewDisplayRepairTarget] = []
    for dimension in ReviewDimension:
        score = score_map[dimension]
        venue_weight = venue_profile.scoring_weights[dimension]
        score_gap = max(0, 5 - score.score)
        confidence_gap = max(0.0, 0.75 - score.confidence)
        priority_score = round(score_gap * venue_weight + confidence_gap * venue_weight * 2, 2)
        if priority_score <= 0:
            continue
        targets.append(
            ReviewDisplayRepairTarget(
                dimension=dimension,
                score=score.score,
                confidence=score.confidence,
                venue_weight=round(venue_weight, 2),
                priority_score=priority_score,
                issue=_repair_issue_label(score_gap, confidence_gap),
                reason=_compact(score.reason),
                action=_repair_next_move(dimension, score_gap, confidence_gap),
            )
        )

    return sorted(
        targets,
        key=lambda target: (-target.priority_score, target.score, target.confidence, target.dimension.value),
    )[:limit]


def _repair_issue_label(score_gap: int, confidence_gap: float) -> str:
    if score_gap >= 2 and confidence_gap > 0:
        return "low_score_and_confidence"
    if score_gap >= 2:
        return "low_score"
    if confidence_gap > 0:
        return "low_confidence"
    return "polish"


def _repair_next_move(dimension: ReviewDimension, score_gap: int, confidence_gap: float) -> str:
    if confidence_gap > 0 and score_gap <= 1:
        return f"Add checkable support for {dimension.value} before treating the score as stable."
    actions = {
        ReviewDimension.venue_fit: "Make the submission's fit with the venue explicit instead of relying on tone alone.",
        ReviewDimension.core_claim_clarity: "State the core claim as a testable sentence and keep later sections anchored to it.",
        ReviewDimension.structural_integrity: "Repair missing or thin sections so the argument has a readable path.",
        ReviewDimension.method_or_reasoning_legibility: "Make the method or reasoning path traceable enough for another reader to inspect.",
        ReviewDimension.evidence_checkability: "Add concrete evidence, citations, examples, or measurement traces that can be checked.",
        ReviewDimension.result_payload: "Turn the premise into a payload: result, observation, artifact, or reusable insight.",
        ReviewDimension.limitation_honesty: "Name the limits directly so the absurd framing does not hide weak boundaries.",
        ReviewDimension.zhenghuo_execution: "Tighten the absurd execution so the bit serves the argument.",
        ReviewDimension.absurd_originality: "Sharpen the premise so it feels specific, not merely random.",
        ReviewDimension.meme_to_argument_conversion: "Show how the meme becomes an argument with stakes and evidence.",
        ReviewDimension.community_discussion_value: "Make the community-facing takeaway easier to quote, debate, or reuse.",
        ReviewDimension.overall_merit: "Resolve the highest-impact weaknesses before asking for a stronger verdict.",
    }
    if score_gap <= 1:
        return f"Polish {dimension.value}; it is close but still below the top band."
    return actions[dimension]


def _fermentation_queue_triage(
    review: ReviewOutput,
    gates: list[ReviewDisplayGate],
    signal_panels: list[ReviewDisplayScoreGroup],
    low_confidence_dimensions: list[ReviewDimension],
) -> ReviewDisplayTriage:
    gate_map = {gate.name: gate for gate in gates}
    first_author_chore = _first_text(review.required_revisions)

    if _gate_needs_review(gate_map, "risk_flags"):
        return ReviewDisplayTriage(
            queue_priority=100,
            lane="human_risk_review",
            primary_gate="risk_flags",
            primary_revision=first_author_chore,
            action="Send to human risk review before reading it as a venue-fit submission.",
        )

    if _gate_needs_review(gate_map, "hard_failures"):
        return ReviewDisplayTriage(
            queue_priority=95,
            lane="blocked_before_review",
            primary_gate="hard_failures",
            primary_revision=first_author_chore,
            action="Repair hard failures before running or trusting a full review.",
        )

    if _gate_needs_review(gate_map, "agent_failures"):
        return ReviewDisplayTriage(
            queue_priority=85,
            lane="degraded_review",
            primary_gate="agent_failures",
            primary_revision=first_author_chore,
            action="Inspect or rerun failed panels before using this verdict operationally.",
        )

    if low_confidence_dimensions:
        first_dimension = low_confidence_dimensions[0]
        return ReviewDisplayTriage(
            queue_priority=80,
            lane="human_confidence_check",
            primary_score_group=_signal_panel_for_dimension(signal_panels, first_dimension),
            primary_revision=first_author_chore,
            action=f"Check low-confidence advancement signal: {first_dimension.value}.",
        )

    weak_panel = _first_signal_panel_with_status(signal_panels, "weak")
    if weak_panel is not None:
        return ReviewDisplayTriage(
            queue_priority=75,
            lane="author_revision",
            primary_revision=first_author_chore,
            primary_score_group=weak_panel.group_id,
            action=weak_panel.recommended_action,
        )

    readiness_gate = _first_needs_review_gate(
        gate_map,
        (
            "format_compliance",
            "citation_traceability",
            "ai_disclosure_integrity",
            "safety_notice_presence",
        ),
    )
    if readiness_gate is not None:
        return ReviewDisplayTriage(
            queue_priority=70,
            lane="submission_readiness",
            primary_gate=readiness_gate.name,
            primary_revision=first_author_chore,
            action=_readiness_action(readiness_gate.name),
        )

    if review.final_recommendation in {
        RecommendationLabel.ADVANCE_TO_FULL_REVIEW,
        RecommendationLabel.ADVANCE_WITH_PAYLOAD_RESERVATIONS,
    }:
        return ReviewDisplayTriage(
            queue_priority=10,
            lane="ready_for_next_stage",
            primary_revision=first_author_chore,
            action=_advance_action(review.final_recommendation, first_author_chore),
        )

    if first_author_chore is not None:
        return ReviewDisplayTriage(
            queue_priority=55,
            lane="author_revision",
            primary_revision=first_author_chore,
            action=f"Start with revision: {first_author_chore}",
        )

    watch_panel = _first_signal_panel_with_status(signal_panels, "watch")
    if watch_panel is not None:
        return ReviewDisplayTriage(
            queue_priority=35,
            lane="editor_watch",
            primary_score_group=watch_panel.group_id,
            action=watch_panel.recommended_action,
        )

    return ReviewDisplayTriage(
        queue_priority=10,
        lane="ready_for_next_stage",
        primary_revision=first_author_chore,
        action="No blocking display issue remains; move it to the next editorial queue.",
    )


def _gate_needs_review(gates_by_name: dict[str, ReviewDisplayGate], name: str) -> bool:
    gate = gates_by_name.get(name)
    return gate is not None and gate.status == "needs_review"


def _first_needs_review_gate(
    gates_by_name: dict[str, ReviewDisplayGate],
    names: tuple[str, ...],
) -> ReviewDisplayGate | None:
    for name in names:
        gate = gates_by_name.get(name)
        if gate is not None and gate.status == "needs_review":
            return gate
    return None


def _first_signal_panel_with_status(
    signal_panels: list[ReviewDisplayScoreGroup],
    status: str,
) -> ReviewDisplayScoreGroup | None:
    candidates = [panel for panel in signal_panels if panel.status == status]
    if not candidates:
        return None
    return min(candidates, key=lambda panel: (panel.mean_score, panel.mean_confidence, panel.group_id))


def _signal_panel_for_dimension(
    signal_panels: list[ReviewDisplayScoreGroup],
    dimension: ReviewDimension,
) -> str | None:
    for panel in signal_panels:
        if dimension in panel.dimensions:
            return panel.group_id
    return None


def _readiness_action(gate_name: str) -> str:
    actions = {
        "format_compliance": "Repair missing manuscript sections before publishing the intake card.",
        "citation_traceability": "Add references or evidence pointers before treating the payload as checkable.",
        "ai_disclosure_integrity": "Add metadata.ai_use_statement before publishing the intake card.",
        "safety_notice_presence": "Add metadata.safety_notice before publishing the intake card.",
    }
    return actions.get(gate_name, f"Resolve {gate_name} before publishing the intake card.")


def _advance_action(recommendation: RecommendationLabel, first_revision: str | None) -> str:
    if recommendation == RecommendationLabel.ADVANCE_WITH_PAYLOAD_RESERVATIONS:
        return "Advance with payload reservations and keep the first revision in the next-stage brief."
    if first_revision:
        return "Advance to full review; carry the first revision into the next-stage brief."
    return "Advance to full review."


def _first_text(items: Iterable[str]) -> str | None:
    for item in items:
        normalized = _compact(item)
        if normalized:
            return normalized
    return None


def _missing_format_items(manuscript: ManuscriptInput, review: ReviewOutput) -> list[str]:
    missing: list[str] = []
    if not manuscript.title.strip():
        missing.append("title")
    if not manuscript.abstract.strip():
        missing.append("abstract")
    if not manuscript.body.strip():
        missing.append("body")

    body_lower = manuscript.body.lower()
    for section in review.resolved_venue_profile.required_sections:
        normalized = section.strip().lower()
        if normalized in {"title", "abstract", "body"}:
            continue
        if normalized and normalized not in body_lower:
            missing.append(normalized)
    return sorted(set(missing))


def _metadata_text(manuscript: ManuscriptInput, key: str) -> str:
    if not manuscript.metadata:
        return ""
    value = manuscript.metadata.get(key)
    if value is None:
        return ""
    return str(value).strip()


def _evidence_strings(items: Iterable[EvidenceItem]) -> list[str]:
    return [_compact(f"{item.excerpt} ({item.source_section or item.source_type.value})") for item in items]


def _list_detail(items: Iterable[object]) -> str:
    sediment = [_compact(item) for item in items if str(item)]
    if not sediment:
        return "none"
    return "; ".join(sediment)


def _compact(value: object) -> str:
    return " ".join(str(value).split())
