"""Canonical schemas for manuscripts, agent outputs, and final reviews."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ContractModel(BaseModel):
    """Base schema that forbids undeclared fields to keep contracts stable."""

    model_config = ConfigDict(extra="forbid")


class ReviewDimension(str, Enum):
    """Supported rubric dimensions for venue-aware absurd review."""

    venue_fit = "venue_fit"
    core_claim_clarity = "core_claim_clarity"
    structural_integrity = "structural_integrity"
    method_or_reasoning_legibility = "method_or_reasoning_legibility"
    evidence_checkability = "evidence_checkability"
    result_payload = "result_payload"
    limitation_honesty = "limitation_honesty"
    zhenghuo_execution = "zhenghuo_execution"
    absurd_originality = "absurd_originality"
    meme_to_argument_conversion = "meme_to_argument_conversion"
    community_discussion_value = "community_discussion_value"
    overall_merit = "overall_merit"


class RecommendationLabel(str, Enum):
    """Allowed screening-decision labels."""

    ADVANCE_TO_FULL_REVIEW = "ADVANCE_TO_FULL_REVIEW"
    ADVANCE_WITH_PAYLOAD_RESERVATIONS = "ADVANCE_WITH_PAYLOAD_RESERVATIONS"
    BORDERLINE_FOR_FULL_REVIEW = "BORDERLINE_FOR_FULL_REVIEW"
    REVISION_REQUIRED_BEFORE_REVIEW = "REVISION_REQUIRED_BEFORE_REVIEW"
    REJECT_AS_EMPTY_GIMMICK = "REJECT_AS_EMPTY_GIMMICK"
    REJECT_AS_INCOHERENT_SLUDGE = "REJECT_AS_INCOHERENT_SLUDGE"
    ESCALATE_FOR_HUMAN_RISK_CHECK = "ESCALATE_FOR_HUMAN_RISK_CHECK"


class VenuePresetName(str, Enum):
    """Built-in venue preset identifiers."""

    SHIT_SCREENING_DEFAULT = "shit-screening-default"
    SHIT_HARDCORE_SCREENING = "shit-hardcore-screening"
    SHIT_ABSTRACT_SCREENING = "shit-abstract-screening"


class PrecheckDecision(str, Enum):
    """Allowed precheck outcomes."""

    PASS = "pass"
    REVISION_REQUIRED = "revision_required"
    REJECT = "reject"


class EvidenceSourceType(str, Enum):
    """Allowed provenance labels for quoted or summarized evidence."""

    manuscript = "manuscript"
    panel = "panel"
    rule = "rule"
    system = "system"


class EvidenceItem(ContractModel):
    """One normalized evidence item used in scores and panel outputs."""

    excerpt: str = Field(min_length=1)
    source_type: EvidenceSourceType = EvidenceSourceType.manuscript
    source_section: str | None = None
    note: str | None = None

    @model_validator(mode="before")
    @classmethod
    def coerce_string_item(cls, value: object) -> object:
        """Allow legacy string evidence entries while normalizing to objects."""

        if isinstance(value, str):
            return {"excerpt": value}
        return value


class ReviewDimensionScore(ContractModel):
    """Structured explanation for a single rubric dimension."""

    score: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1)
    supporting_evidence: list[EvidenceItem] = Field(default_factory=list)
    uncertainty_note: str | None = None


class EvidenceDimensionScores(ContractModel):
    """Evidence-panel scores with explicit fields for OpenAI schema compatibility."""

    core_claim_clarity: ReviewDimensionScore
    structural_integrity: ReviewDimensionScore
    method_or_reasoning_legibility: ReviewDimensionScore
    evidence_checkability: ReviewDimensionScore
    result_payload: ReviewDimensionScore
    limitation_honesty: ReviewDimensionScore

    def as_dict(self) -> dict[ReviewDimension, ReviewDimensionScore]:
        """Return the explicit field set as a ReviewDimension-keyed mapping."""

        return {
            ReviewDimension.core_claim_clarity: self.core_claim_clarity,
            ReviewDimension.structural_integrity: self.structural_integrity,
            ReviewDimension.method_or_reasoning_legibility: self.method_or_reasoning_legibility,
            ReviewDimension.evidence_checkability: self.evidence_checkability,
            ReviewDimension.result_payload: self.result_payload,
            ReviewDimension.limitation_honesty: self.limitation_honesty,
        }


class ValueDimensionScores(ContractModel):
    """Value-panel scores with explicit fields for OpenAI schema compatibility."""

    venue_fit: ReviewDimensionScore
    zhenghuo_execution: ReviewDimensionScore
    absurd_originality: ReviewDimensionScore
    meme_to_argument_conversion: ReviewDimensionScore
    community_discussion_value: ReviewDimensionScore
    overall_merit: ReviewDimensionScore

    def as_dict(self) -> dict[ReviewDimension, ReviewDimensionScore]:
        """Return the explicit field set as a ReviewDimension-keyed mapping."""

        return {
            ReviewDimension.venue_fit: self.venue_fit,
            ReviewDimension.zhenghuo_execution: self.zhenghuo_execution,
            ReviewDimension.absurd_originality: self.absurd_originality,
            ReviewDimension.meme_to_argument_conversion: self.meme_to_argument_conversion,
            ReviewDimension.community_discussion_value: self.community_discussion_value,
            ReviewDimension.overall_merit: self.overall_merit,
        }


class AllDimensionScores(ContractModel):
    """Full 12-dimension score set with explicit fields for stable schemas."""

    venue_fit: ReviewDimensionScore
    core_claim_clarity: ReviewDimensionScore
    structural_integrity: ReviewDimensionScore
    method_or_reasoning_legibility: ReviewDimensionScore
    evidence_checkability: ReviewDimensionScore
    result_payload: ReviewDimensionScore
    limitation_honesty: ReviewDimensionScore
    zhenghuo_execution: ReviewDimensionScore
    absurd_originality: ReviewDimensionScore
    meme_to_argument_conversion: ReviewDimensionScore
    community_discussion_value: ReviewDimensionScore
    overall_merit: ReviewDimensionScore

    def as_dict(self) -> dict[ReviewDimension, ReviewDimensionScore]:
        """Return the explicit field set as a ReviewDimension-keyed mapping."""

        return {
            dimension: getattr(self, dimension.value)
            for dimension in ReviewDimension
        }


class RuleHit(ContractModel):
    """Rule-engine trace for a postprocessing decision."""

    code: str
    description: str
    effect: str
    triggered: bool = True


class AgentFailure(ContractModel):
    """Structured record for a degraded subagent call."""

    agent_name: str
    error_type: str
    message: str


class RecommendationPolicy(ContractModel):
    """Thresholds used when converting scores into a screening decision."""

    advance_to_full_review_min_final_score: float = Field(ge=1.0, le=5.0)
    advance_with_payload_reservations_min_final_score: float = Field(ge=1.0, le=5.0)
    borderline_for_full_review_min_final_score: float = Field(ge=1.0, le=5.0)
    payload_floor_for_advance: int = Field(ge=1, le=5)
    venue_fit_floor_for_advance: int = Field(ge=1, le=5)

    @model_validator(mode="after")
    def ensure_descending_thresholds(self) -> "RecommendationPolicy":
        """Require stronger recommendations to have higher score thresholds."""

        if self.advance_to_full_review_min_final_score < self.advance_with_payload_reservations_min_final_score:
            raise ValueError(
                "advance_to_full_review_min_final_score must be >= advance_with_payload_reservations_min_final_score"
            )
        if self.advance_with_payload_reservations_min_final_score < self.borderline_for_full_review_min_final_score:
            raise ValueError(
                "advance_with_payload_reservations_min_final_score must be >= borderline_for_full_review_min_final_score"
            )
        return self


class VenueProfile(ContractModel):
    """Venue-specific configuration for review scoring and recommendation policy."""

    preset_name: VenuePresetName | None = None
    venue_name: str
    tone: str
    required_sections: list[str]
    minimum_reviewable_characters: int | None = Field(default=None, gt=0)
    scoring_weights: dict[ReviewDimension, float]
    rejection_rules: list[str]
    recommendation_policy: RecommendationPolicy

    @field_validator("required_sections")
    @classmethod
    def ensure_sections(cls, value: list[str]) -> list[str]:
        """Require at least one expected manuscript section."""

        if not value:
            raise ValueError("required_sections must not be empty")
        return value

    @field_validator("scoring_weights")
    @classmethod
    def ensure_weights_cover_all_dimensions(
        cls, value: dict[ReviewDimension, float]
    ) -> dict[ReviewDimension, float]:
        """Require a non-negative weight for each scoring dimension."""

        missing = {dimension for dimension in ReviewDimension if dimension not in value}
        if missing:
            raise ValueError(f"missing scoring weights for: {sorted(item.value for item in missing)}")
        if any(weight < 0 for weight in value.values()):
            raise ValueError("scoring weights must be non-negative")
        if sum(value.values()) <= 0:
            raise ValueError("scoring weights must sum to a positive value")
        return value

    @classmethod
    def from_builtin_preset(
        cls,
        preset: VenuePresetName | str | None = None,
        *,
        default_minimum_reviewable_characters: int | None = None,
    ) -> "VenueProfile":
        """Return a built-in screening preset for the current review agent."""

        preset_name = VenuePresetName(preset or VenuePresetName.SHIT_SCREENING_DEFAULT)

        common_rules = [
            "missing_title_or_abstract_or_body_is_hard_failure",
            "no_core_claim_caps_overall_at_two",
            "no_checkable_evidence_caps_evidence_at_two",
            "gimmick_without_payload_caps_overall_at_three",
            "unsafe_or_abusive_content_sets_risk_flag",
            "low_confidence_advancement_gate",
        ]

        if preset_name is VenuePresetName.SHIT_HARDCORE_SCREENING:
            return cls(
                preset_name=preset_name,
                venue_name="S.H.I.T Hardcore Screening Track",
                tone="Independent initial screening for rigorous absurd manuscripts with real payload, method, and checkable evidence.",
                required_sections=["title", "abstract", "body", "method", "results", "conclusion", "limitations"],
                minimum_reviewable_characters=1500,
                scoring_weights={
                    ReviewDimension.venue_fit: 0.9,
                    ReviewDimension.core_claim_clarity: 1.25,
                    ReviewDimension.structural_integrity: 1.15,
                    ReviewDimension.method_or_reasoning_legibility: 1.25,
                    ReviewDimension.evidence_checkability: 1.25,
                    ReviewDimension.result_payload: 1.3,
                    ReviewDimension.limitation_honesty: 0.9,
                    ReviewDimension.zhenghuo_execution: 0.7,
                    ReviewDimension.absurd_originality: 0.8,
                    ReviewDimension.meme_to_argument_conversion: 0.85,
                    ReviewDimension.community_discussion_value: 0.7,
                    ReviewDimension.overall_merit: 1.35,
                },
                rejection_rules=common_rules,
                recommendation_policy=RecommendationPolicy(
                    advance_to_full_review_min_final_score=4.2,
                    advance_with_payload_reservations_min_final_score=3.7,
                    borderline_for_full_review_min_final_score=2.9,
                    payload_floor_for_advance=3,
                    venue_fit_floor_for_advance=3,
                ),
            )

        if preset_name is VenuePresetName.SHIT_ABSTRACT_SCREENING:
            return cls(
                preset_name=preset_name,
                venue_name="S.H.I.T Abstract Screening Track",
                tone="Independent initial screening for playful, readable, discussable, and safely absurd submissions.",
                required_sections=["title", "abstract", "body", "conclusion", "limitations"],
                minimum_reviewable_characters=800,
                scoring_weights={
                    ReviewDimension.venue_fit: 1.1,
                    ReviewDimension.core_claim_clarity: 1.0,
                    ReviewDimension.structural_integrity: 1.0,
                    ReviewDimension.method_or_reasoning_legibility: 0.9,
                    ReviewDimension.evidence_checkability: 0.8,
                    ReviewDimension.result_payload: 1.0,
                    ReviewDimension.limitation_honesty: 0.8,
                    ReviewDimension.zhenghuo_execution: 1.25,
                    ReviewDimension.absurd_originality: 1.2,
                    ReviewDimension.meme_to_argument_conversion: 1.25,
                    ReviewDimension.community_discussion_value: 1.1,
                    ReviewDimension.overall_merit: 1.2,
                },
                rejection_rules=common_rules,
                recommendation_policy=RecommendationPolicy(
                    advance_to_full_review_min_final_score=4.0,
                    advance_with_payload_reservations_min_final_score=3.5,
                    borderline_for_full_review_min_final_score=2.8,
                    payload_floor_for_advance=2,
                    venue_fit_floor_for_advance=3,
                ),
            )

        return cls(
            preset_name=preset_name,
            venue_name="S.H.I.T Initial Screening Desk",
            tone="Independent initial screening for absurd submissions that may contain real payload and deserve the next review stage.",
            required_sections=["title", "abstract", "body", "conclusion", "limitations"],
            minimum_reviewable_characters=default_minimum_reviewable_characters,
            scoring_weights={
                ReviewDimension.venue_fit: 1.0,
                ReviewDimension.core_claim_clarity: 1.2,
                ReviewDimension.structural_integrity: 1.1,
                ReviewDimension.method_or_reasoning_legibility: 1.1,
                ReviewDimension.evidence_checkability: 1.0,
                ReviewDimension.result_payload: 1.25,
                ReviewDimension.limitation_honesty: 0.8,
                ReviewDimension.zhenghuo_execution: 1.0,
                ReviewDimension.absurd_originality: 1.0,
                ReviewDimension.meme_to_argument_conversion: 1.1,
                ReviewDimension.community_discussion_value: 0.9,
                ReviewDimension.overall_merit: 1.35,
            },
            rejection_rules=common_rules,
            recommendation_policy=RecommendationPolicy(
                advance_to_full_review_min_final_score=4.2,
                advance_with_payload_reservations_min_final_score=3.7,
                borderline_for_full_review_min_final_score=2.8,
                payload_floor_for_advance=3,
                venue_fit_floor_for_advance=3,
            ),
        )

    @classmethod
    def default_screening_profile(
        cls,
        minimum_reviewable_characters: int | None = None,
    ) -> "VenueProfile":
        """Return the built-in default initial-screening profile."""

        return cls.from_builtin_preset(
            VenuePresetName.SHIT_SCREENING_DEFAULT,
            default_minimum_reviewable_characters=minimum_reviewable_characters,
        )

    @classmethod
    def default_absurd_journal(cls) -> "VenueProfile":
        """Backward-compatible alias for the default screening profile."""

        return cls.default_screening_profile()


class ManuscriptInput(ContractModel):
    """Incoming manuscript payload for review."""

    manuscript_id: str = Field(min_length=1)
    title: str = ""
    abstract: str = ""
    body: str = ""
    authors: list[str] | None = None
    references: list[str] | None = None
    venue_profile: VenueProfile | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("manuscript_id", mode="before")
    @classmethod
    def normalise_manuscript_id(cls, value: object) -> object:
        """Trim manuscript identifiers before enforcing the non-empty contract."""

        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("title", "abstract", "body", mode="before")
    @classmethod
    def normalise_text(cls, value: str | None) -> str:
        """Trim nullable strings while preserving missing-content detection."""

        return (value or "").strip()


class PrecheckOutput(ContractModel):
    """Precheck verdict before expensive multi-agent review begins."""

    decision: PrecheckDecision
    minimum_reviewable: bool
    hard_failures: list[str] = Field(default_factory=list)
    missing_sections: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class EvidenceAgentOutput(ContractModel):
    """Evidence-focused subreview with claim and reasoning diagnostics."""

    paper_summary: str
    extracted_core_claim: str
    argument_status: str
    evidence_snippets: list[EvidenceItem] = Field(default_factory=list)
    major_strengths: list[str] = Field(default_factory=list)
    major_weaknesses: list[str] = Field(default_factory=list)
    required_revisions: list[str] = Field(default_factory=list)
    optional_revisions: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    dimension_scores: EvidenceDimensionScores


class ValueAgentOutput(ContractModel):
    """Absurdity-value subreview for zhenghuo quality and venue fit."""

    zhenghuo_verdict: str
    novelty_label: str
    major_strengths: list[str] = Field(default_factory=list)
    major_weaknesses: list[str] = Field(default_factory=list)
    required_revisions: list[str] = Field(default_factory=list)
    optional_revisions: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    dimension_scores: ValueDimensionScores


class FinalMetaReviewOutput(ContractModel):
    """Meta-reviewer aggregation before rules finalize the verdict."""

    paper_summary: str
    extracted_core_claim: str
    scores_by_dimension: AllDimensionScores
    major_strengths: list[str] = Field(default_factory=list)
    major_weaknesses: list[str] = Field(default_factory=list)
    required_revisions: list[str] = Field(default_factory=list)
    optional_revisions: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    final_rationale: str
    community_facing_blurb: str


class DryRunOutput(ContractModel):
    """Dry-run result that stops after validation and precheck."""

    manuscript_id: str
    accepted_for_full_review: bool
    precheck: PrecheckOutput
    venue_profile: VenueProfile


class VenueValidationResponse(ContractModel):
    """Response for validating a custom venue profile."""

    valid: bool
    venue_name: str
    normalized_profile: VenueProfile


class RawAgentOutputStatus(str, Enum):
    """Supported statuses for captured raw agent outputs."""

    success = "success"
    failed = "failed"
    fallback = "fallback"


class RawAgentArtifactType(str, Enum):
    """Typed payload categories for stored raw agent outputs."""

    precheck_output = "precheck_output"
    evidence_output = "evidence_output"
    value_output = "value_output"
    meta_output = "meta_output"


class RawAgentOutputEnvelope(ContractModel):
    """Stable wrapper for raw agent payloads kept for debugging and audits."""

    status: RawAgentOutputStatus
    artifact_type: RawAgentArtifactType | None = None
    payload: PrecheckOutput | EvidenceAgentOutput | ValueAgentOutput | FinalMetaReviewOutput | None = None


class RiskAuditAction(str, Enum):
    """Actions produced by the risk-audit workflow."""

    CLEAR = "CLEAR"
    FLAG_FOR_HUMAN_REVIEW = "FLAG_FOR_HUMAN_REVIEW"
    BLOCK_BEFORE_REVIEW = "BLOCK_BEFORE_REVIEW"


class VenueFitAction(str, Enum):
    """Actions produced by the venue-fit audit workflow."""

    STRONG_FIT = "STRONG_FIT"
    BORDERLINE_FIT = "BORDERLINE_FIT"
    MISALIGNED = "MISALIGNED"
    BLOCKED_BY_RISK = "BLOCKED_BY_RISK"
    INSUFFICIENT_FOR_FIT_JUDGMENT = "INSUFFICIENT_FOR_FIT_JUDGMENT"


class RiskAuditOutput(ContractModel):
    """Result of a lightweight risk-focused workflow centered on intake safety."""

    workflow_session_id: str
    manuscript_id: str
    resolved_venue_profile: VenueProfile
    local_precheck: PrecheckOutput
    llm_precheck: PrecheckOutput | None = None
    effective_precheck: PrecheckOutput
    risk_flags: list[str] = Field(default_factory=list)
    action: RiskAuditAction
    rationale: str
    raw_agent_outputs: dict[str, RawAgentOutputEnvelope] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VenueFitAuditOutput(ContractModel):
    """Result of a lightweight venue-fit workflow centered on cultural alignment."""

    workflow_session_id: str
    manuscript_id: str
    resolved_venue_profile: VenueProfile
    local_precheck: PrecheckOutput
    llm_precheck: PrecheckOutput | None = None
    effective_precheck: PrecheckOutput
    value_review: ValueAgentOutput | None = None
    risk_flags: list[str] = Field(default_factory=list)
    venue_fit_score: int = Field(ge=1, le=5)
    meme_to_argument_score: int = Field(ge=1, le=5)
    zhenghuo_execution_score: int = Field(ge=1, le=5)
    action: VenueFitAction
    rationale: str
    top_strengths: list[str] = Field(default_factory=list)
    top_weaknesses: list[str] = Field(default_factory=list)
    raw_agent_outputs: dict[str, RawAgentOutputEnvelope] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReviewOutput(ContractModel):
    """Final review payload returned by API and CLI."""

    workflow_session_id: str
    manuscript_id: str
    resolved_venue_profile: VenueProfile
    paper_summary: str
    extracted_core_claim: str
    scores_by_dimension: AllDimensionScores
    hard_failures: list[str] = Field(default_factory=list)
    major_strengths: list[str] = Field(default_factory=list)
    major_weaknesses: list[str] = Field(default_factory=list)
    required_revisions: list[str] = Field(default_factory=list)
    optional_revisions: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    rule_hits: list[RuleHit] = Field(default_factory=list)
    agent_failures: list[AgentFailure] = Field(default_factory=list)
    final_score: float = Field(ge=1.0, le=5.0)
    final_recommendation: RecommendationLabel
    final_rationale: str
    human_readable_review: str
    community_facing_blurb: str
    raw_agent_outputs: dict[str, RawAgentOutputEnvelope] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ErrorResponse(ContractModel):
    """Uniform API error envelope."""

    error_code: str
    message: str
    details: dict[str, Any] | None = None


class HealthResponse(ContractModel):
    """Health-check envelope for API monitoring and local debugging."""

    status: str
    service: str
    provider_backend: str
    default_model: str
    database_ok: bool
    provider_configured: bool


class WorkflowEdge(ContractModel):
    """One directed dependency edge in a registered workflow graph."""

    source: str
    target: str
    condition: str | None = None


class WorkflowInfo(ContractModel):
    """Runtime-exposed metadata for one registered workflow."""

    workflow_id: str
    description: str
    node_ids: list[str] = Field(default_factory=list)
    edges: list[WorkflowEdge] = Field(default_factory=list)
    parallel_groups: list[list[str]] = Field(default_factory=list)
    artifact_keys: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class PersistedReviewRecord(ContractModel):
    """Database-friendly wrapper for persisted review records."""

    run_id: str
    review: ReviewOutput
    request_payload: ManuscriptInput


class ReviewRunSummary(ContractModel):
    """Lightweight query result for persisted review runs."""

    run_id: str
    manuscript_id: str
    created_at: datetime
    final_score: float = Field(ge=1.0, le=5.0)
    final_recommendation: RecommendationLabel
    resolved_venue_profile: VenueProfile


class ReviewDisplayGate(ContractModel):
    """One display-ready gate row for dashboards and intake cards."""

    name: str
    status: Literal["pass", "needs_review", "info"]
    detail: str


class ReviewDisplayScoreRow(ContractModel):
    """One display-ready rubric row with short evidence strings."""

    dimension: ReviewDimension
    score: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)


class ReviewDisplayScoreGroup(ContractModel):
    """Grouped score summary for dashboard sections."""

    group_id: str
    label: str
    dimensions: list[ReviewDimension]
    mean_score: float = Field(ge=1.0, le=5.0)
    mean_confidence: float = Field(ge=0.0, le=1.0)
    status: Literal["strong", "watch", "weak"]
    weakest_dimension: ReviewDimension
    weakest_score: int = Field(ge=1, le=5)
    recommended_action: str


class ReviewDisplayRepairTarget(ContractModel):
    """Venue-weighted dimension to fix or polish first."""

    dimension: ReviewDimension
    score: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0.0, le=1.0)
    venue_weight: float = Field(ge=0.0)
    priority_score: float = Field(ge=0.0)
    issue: Literal["low_score", "low_confidence", "low_score_and_confidence", "polish"]
    reason: str
    action: str


class ReviewDisplayTriage(ContractModel):
    """Single next-action summary for editor queues."""

    queue_priority: int = Field(ge=0, le=100)
    lane: Literal[
        "human_risk_review",
        "blocked_before_review",
        "degraded_review",
        "human_confidence_check",
        "submission_readiness",
        "author_revision",
        "editor_watch",
        "ready_for_next_stage",
    ]
    primary_gate: str | None = None
    primary_revision: str | None = None
    primary_score_group: str | None = None
    action: str


class ReviewDisplayOutput(ContractModel):
    """Front-end friendly projection of a persisted review."""

    run_id: str
    workflow_session_id: str
    manuscript_id: str
    recommendation: RecommendationLabel
    final_score: float = Field(ge=1.0, le=5.0)
    weighted_confidence: float = Field(ge=0.0, le=1.0)
    calibration_status: Literal["high_confidence", "medium_confidence", "low_confidence", "human_check_recommended"]
    suggested_stage: str
    venue_name: str
    venue_preset: str | None = None
    summary: str
    core_claim: str
    community_blurb: str
    triage: ReviewDisplayTriage
    gates: list[ReviewDisplayGate] = Field(default_factory=list)
    low_confidence_dimensions: list[ReviewDimension] = Field(default_factory=list)
    score_matrix: list[ReviewDisplayScoreRow] = Field(default_factory=list)
    score_groups: list[ReviewDisplayScoreGroup] = Field(default_factory=list)
    repair_targets: list[ReviewDisplayRepairTarget] = Field(default_factory=list)
    required_revisions: list[str] = Field(default_factory=list)
    optional_revisions: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    rule_hits: list[str] = Field(default_factory=list)
    created_at: datetime


class ReviewDisplaySummary(ContractModel):
    """Queue-list projection for persisted review runs."""

    run_id: str
    manuscript_id: str
    created_at: datetime
    recommendation: RecommendationLabel
    final_score: float = Field(ge=1.0, le=5.0)
    weighted_confidence: float = Field(ge=0.0, le=1.0)
    calibration_status: Literal["high_confidence", "medium_confidence", "low_confidence", "human_check_recommended"]
    suggested_stage: str
    venue_name: str
    venue_preset: str | None = None
    triage: ReviewDisplayTriage
    top_repair_target: ReviewDisplayRepairTarget | None = None
    needs_review_gates: list[str] = Field(default_factory=list)


class ReviewDisplayRepairHotspot(ContractModel):
    """Aggregate repair pressure for one rubric dimension."""

    dimension: ReviewDimension
    count: int = Field(ge=1)
    max_priority_score: float = Field(ge=0.0)
    average_priority_score: float = Field(ge=0.0)


class ReviewDisplayQueueOverview(ContractModel):
    """Dashboard-level aggregate for a display queue sample."""

    total_reviews: int = Field(ge=0)
    lane_counts: dict[str, int] = Field(default_factory=dict)
    gate_counts: dict[str, int] = Field(default_factory=dict)
    needs_human_review: int = Field(ge=0)
    ready_for_next_stage: int = Field(ge=0)
    average_final_score: float | None = None
    average_weighted_confidence: float | None = None
    top_repair_hotspots: list[ReviewDisplayRepairHotspot] = Field(default_factory=list)


class AgentLogRecord(ContractModel):
    """Database-friendly wrapper for agent execution logs."""

    run_id: str
    agent_name: str
    status: str
    prompt_version: str
    prompt_hash: str
    latency_ms: int
    error_message: str | None = None
    payload: dict[str, Any] | None = None


class WorkflowSessionStatus(str, Enum):
    """Lifecycle states for a workflow session."""

    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class WorkflowStepStatus(str, Enum):
    """Execution states for one workflow node."""

    succeeded = "succeeded"
    failed = "failed"
    skipped = "skipped"


class WorkflowStepRecord(ContractModel):
    """Persisted execution record for one workflow step."""

    node_id: str
    status: WorkflowStepStatus
    started_at: datetime
    finished_at: datetime
    details: dict[str, Any] | None = None


class WorkflowArtifactRecord(ContractModel):
    """Persisted intermediate artifact generated during workflow execution."""

    artifact_key: str
    payload: "WorkflowArtifactEnvelope"
    created_at: datetime


class WorkflowSessionRecord(ContractModel):
    """Normalized workflow session envelope for runtime and storage."""

    session_id: str
    workflow_id: str
    status: WorkflowSessionStatus
    created_at: datetime
    updated_at: datetime
    request_payload: dict[str, Any]
    final_output: dict[str, Any] | None = None
    steps: list[WorkflowStepRecord] = Field(default_factory=list)
    artifacts: list[WorkflowArtifactRecord] = Field(default_factory=list)


class WorkflowSessionSummary(ContractModel):
    """Lightweight query result for persisted workflow sessions."""

    session_id: str
    workflow_id: str
    status: WorkflowSessionStatus
    manuscript_id: str
    created_at: datetime
    updated_at: datetime
    final_output_type: str | None = None


class RuleHitCollection(ContractModel):
    """Typed wrapper for rule-trace artifacts."""

    items: list[RuleHit] = Field(default_factory=list)


class WorkflowArtifactType(str, Enum):
    """Supported typed payload classes for workflow artifacts."""

    venue_profile = "venue_profile"
    precheck_output = "precheck_output"
    agent_output = "agent_output"
    rule_trace = "rule_trace"
    review_output = "review_output"
    risk_audit_output = "risk_audit_output"
    venue_fit_audit_output = "venue_fit_audit_output"


class WorkflowArtifactEnvelope(ContractModel):
    """Typed envelope stored for each workflow artifact."""

    artifact_type: WorkflowArtifactType
    payload: (
        VenueProfile
        | PrecheckOutput
        | RawAgentOutputEnvelope
        | RuleHitCollection
        | ReviewOutput
        | RiskAuditOutput
        | VenueFitAuditOutput
    )


def build_low_confidence_score(reason: str) -> ReviewDimensionScore:
    """Return a fallback score when a panel result is missing."""

    return ReviewDimensionScore(
        score=2,
        confidence=0.25,
        reason=reason,
        supporting_evidence=[],
        uncertainty_note="Deterministic fallback used because structured panel output was missing.",
    )


def build_evidence_item(
    excerpt: str,
    *,
    source_type: EvidenceSourceType = EvidenceSourceType.manuscript,
    source_section: str | None = None,
    note: str | None = None,
) -> EvidenceItem:
    """Construct one normalized evidence item."""

    return EvidenceItem(
        excerpt=excerpt,
        source_type=source_type,
        source_section=source_section,
        note=note,
    )


def build_all_dimension_scores(
    scores_by_dimension: dict[ReviewDimension, ReviewDimensionScore],
) -> AllDimensionScores:
    """Convert an internal ReviewDimension-keyed mapping into the public score model."""

    return AllDimensionScores(
        **{dimension.value: scores_by_dimension[dimension] for dimension in ReviewDimension}
    )
