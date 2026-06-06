"""Markdown report rendering for review outputs."""

from __future__ import annotations

from collections.abc import Iterable

from glorious_mess_reviewer.display import build_review_display, project_review_stage, review_confidence_status
from glorious_mess_reviewer.scoring import compute_weighted_confidence, find_low_confidence_advancement_dimensions
from glorious_mess_reviewer.schemas import (
    EvidenceItem,
    ManuscriptInput,
    PersistedReviewRecord,
    ReviewDimension,
    ReviewDisplayOutput,
    ReviewOutput,
)


def render_review_markdown(review: ReviewOutput, *, manuscript: ManuscriptInput | None = None) -> str:
    """Render a review as a compact intake report for editors and authors."""

    display = _display_projection(review, manuscript)
    fermentation_stage = display.suggested_stage if display else project_review_stage(review.final_recommendation)
    score_map = review.scores_by_dimension.as_dict()
    weighted_confidence = (
        display.weighted_confidence if display else compute_weighted_confidence(score_map, review.resolved_venue_profile)
    )
    low_confidence_dimensions = display.low_confidence_dimensions if display else find_low_confidence_advancement_dimensions(score_map)
    lines = [
        f"# Venue-Fit Intake Report: {review.manuscript_id}",
        "",
        f"- Recommendation: `{review.final_recommendation.value}`",
        f"- Final score: `{review.final_score:.2f}`",
        f"- Weighted confidence: `{weighted_confidence:.2f}`",
        f"- Suggested stage: `{fermentation_stage}`",
        f"- Venue preset: `{_preset_name(review)}`",
        f"- Created at: `{review.created_at.isoformat()}`",
        "",
        "## Decision",
        "",
        review.final_rationale,
        "",
        *_display_triage_section(display),
        "## Stage Flow",
        "",
        _fermentation_ladder(fermentation_stage),
        "",
        "## Gate Checklist",
        "",
        "| Gate | Status | Detail |",
        "| --- | --- | --- |",
        *_gate_rows(review, display),
        "",
        "## Confidence Map",
        "",
        "| Signal | Value |",
        "| --- | --- |",
        f"| Weighted confidence | `{weighted_confidence:.2f}` |",
        f"| Low-confidence advancement gates | {_dimension_names_or_none(low_confidence_dimensions)} |",
        f"| Calibration status | `{review_confidence_status(weighted_confidence, low_confidence_dimensions)}` |",
        "",
        "## Manuscript Read",
        "",
        f"- Summary: {review.paper_summary}",
        f"- Core claim: {review.extracted_core_claim}",
        f"- Community blurb: {review.community_facing_blurb}",
        "",
        *_score_group_section(display),
        *_repair_target_section(display),
        "## Score Matrix",
        "",
        "| Dimension | Score | Confidence | Evidence |",
        "| --- | ---: | ---: | --- |",
    ]
    for dimension in ReviewDimension:
        score = score_map[dimension]
        lines.append(
            "| {dimension} | {score} | {confidence:.2f} | {evidence} |".format(
                dimension=dimension.value,
                score=score.score,
                confidence=score.confidence,
                evidence=_evidence_or_none(score.supporting_evidence),
            )
        )

    lines.extend(
        [
            "",
            "## Required Revisions",
            "",
            *_sediment_bullets(review.required_revisions),
            "",
            "## Optional Revisions",
            "",
            *_sediment_bullets(review.optional_revisions),
            "",
            "## Strengths",
            "",
            *_sediment_bullets(review.major_strengths),
            "",
            "## Weaknesses",
            "",
            *_sediment_bullets(review.major_weaknesses),
            "",
        ]
    )
    return "\n".join(lines)


def _display_projection(review: ReviewOutput, manuscript: ManuscriptInput | None) -> ReviewDisplayOutput | None:
    if manuscript is None:
        return None
    return build_review_display(
        PersistedReviewRecord(
            run_id="markdown-report-preview",
            review=review,
            request_payload=manuscript,
        )
    )


def _preset_name(review: ReviewOutput) -> str:
    preset = review.resolved_venue_profile.preset_name
    if preset is None:
        return "custom"
    return preset.value


def _display_triage_section(display: ReviewDisplayOutput | None) -> list[str]:
    if display is None:
        return []
    triage = display.triage
    return [
        "## Queue Triage",
        "",
        "| Signal | Value |",
        "| --- | --- |",
        f"| Lane | `{triage.lane}` |",
        f"| Queue priority | `{triage.queue_priority}` |",
        f"| Primary gate | {_inline_or_none(triage.primary_gate)} |",
        f"| Primary score group | {_inline_or_none(triage.primary_score_group)} |",
        f"| Primary revision | {_table_safe(triage.primary_revision or 'none')} |",
        f"| Next action | {_table_safe(triage.action)} |",
        "",
    ]


def _gate_rows(review: ReviewOutput, display: ReviewDisplayOutput | None) -> list[str]:
    if display is not None:
        return [
            f"| {_table_safe(gate.name)} | `{gate.status}` | {_table_safe(gate.detail)} |"
            for gate in display.gates
        ]
    return [
        _latrine_gate_row("Risk flags", not review.risk_flags, _settle_list_or_none(review.risk_flags)),
        _latrine_gate_row("Hard failures", not review.hard_failures, _settle_list_or_none(review.hard_failures)),
        _latrine_gate_row("Agent failures", not review.agent_failures, _agent_failure_sediment(review)),
        _latrine_gate_row("Rule trace", bool(review.rule_hits), f"{len(review.rule_hits)} rule hit(s)"),
    ]


def _score_group_section(display: ReviewDisplayOutput | None) -> list[str]:
    if display is None:
        return []
    lines = [
        "## Score Groups",
        "",
        "| Group | Status | Mean score | Weakest dimension | Action |",
        "| --- | --- | ---: | --- | --- |",
    ]
    lines.extend(
        "| {group} | `{status}` | {score:.2f} | `{weakest}` | {action} |".format(
            group=_table_safe(group.label),
            status=group.status,
            score=group.mean_score,
            weakest=group.weakest_dimension.value,
            action=_table_safe(group.recommended_action),
        )
        for group in display.score_groups
    )
    lines.append("")
    return lines


def _repair_target_section(display: ReviewDisplayOutput | None) -> list[str]:
    if display is None:
        return []
    lines = [
        "## Repair Targets",
        "",
        "| Dimension | Issue | Score | Confidence | Priority | Action |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    if not display.repair_targets:
        lines.append("| none | none |  |  |  | none |")
    else:
        lines.extend(
            "| `{dimension}` | `{issue}` | {score} | {confidence:.2f} | {priority:.2f} | {action} |".format(
                dimension=target.dimension.value,
                issue=target.issue,
                score=target.score,
                confidence=target.confidence,
                priority=target.priority_score,
                action=_table_safe(target.action),
            )
            for target in display.repair_targets
        )
    lines.append("")
    return lines


def _fermentation_ladder(fermentation_stage: str) -> str:
    ladder_rungs = ["petri_dish_revision", "fermentation", "real_shit_candidate"]
    if fermentation_stage == "human_risk_review":
        return "`Petri Dish` -> `Human risk review` -> `Manual decision required`"
    labels = {
        "petri_dish_revision": "Petri Dish",
        "fermentation": "Fermentation",
        "real_shit_candidate": "Real S.H.*.T candidate",
    }
    return " -> ".join(
        f"**{labels[item]}**" if item == fermentation_stage else f"`{labels[item]}`"
        for item in ladder_rungs
    )


def _latrine_gate_row(name: str, passed: bool, detail: str) -> str:
    status = "pass" if passed else "needs_review"
    return f"| {name} | `{status}` | {detail} |"


def _settle_list_or_none(items: Iterable[str]) -> str:
    sediment = [_table_safe(item) for item in items if str(item)]
    if not sediment:
        return "none"
    return "; ".join(sediment)


def _evidence_or_none(items: Iterable[EvidenceItem]) -> str:
    sediment: list[str] = []
    for item in items:
        source = item.source_section or item.source_type.value
        sediment.append(_table_safe(f"{item.excerpt} ({source})"))
    if not sediment:
        return "none"
    return "; ".join(sediment)


def _dimension_names_or_none(dimensions: Iterable[ReviewDimension]) -> str:
    names = [f"`{dimension.value}`" for dimension in dimensions]
    if not names:
        return "none"
    return ", ".join(names)


def _inline_or_none(value: str | None) -> str:
    if not value:
        return "none"
    return f"`{_table_safe(value)}`"


def _table_safe(value: object) -> str:
    return " ".join(str(value).split()).replace("|", "\\|")


def _agent_failure_sediment(review: ReviewOutput) -> str:
    if not review.agent_failures:
        return "none"
    return _settle_list_or_none(f"{failure.agent_name}: {failure.error_type}" for failure in review.agent_failures)


def _sediment_bullets(items: Iterable[str]) -> list[str]:
    sediment = [str(item) for item in items if str(item)]
    if not sediment:
        return ["- none"]
    return [f"- {item}" for item in sediment]
