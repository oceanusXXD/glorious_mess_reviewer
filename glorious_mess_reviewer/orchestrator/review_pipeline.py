"""Main multi-agent review helpers plus a workflow-backed compatibility facade."""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Awaitable, Generic, TypeVar

from pydantic import BaseModel

from glorious_mess_reviewer.agents.base import AgentCallError
from glorious_mess_reviewer.agents.catalog import ScreeningAgentCatalog
from glorious_mess_reviewer.config.settings import Settings
from glorious_mess_reviewer.prompts import PromptTemplate
from glorious_mess_reviewer.providers import LLMProvider, ProviderError
from glorious_mess_reviewer.scoring import (
    apply_post_review_rules,
    compute_screening_recommendation,
    compute_weighted_final_score,
)
from glorious_mess_reviewer.schemas import (
    AgentFailure,
    DryRunOutput,
    EvidenceAgentOutput,
    EvidenceSourceType,
    FinalMetaReviewOutput,
    ManuscriptInput,
    PrecheckDecision,
    PrecheckOutput,
    RawAgentArtifactType,
    RawAgentOutputEnvelope,
    ReviewDimension,
    ReviewDimensionScore,
    ReviewOutput,
    RiskAuditAction,
    RiskAuditOutput,
    ValueAgentOutput,
    VenueFitAction,
    VenueFitAuditOutput,
    VenueProfile,
    build_all_dimension_scores,
    build_evidence_item,
)
from glorious_mess_reviewer.schemas.contracts import AgentLogRecord
from glorious_mess_reviewer.storage import SQLiteReviewStore
from glorious_mess_reviewer.workflows import ScreeningReviewWorkflow

LOGGER = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


@dataclass
class AgentExecutionResult(Generic[T]):
    """Structured result for one logged agent invocation."""

    result: T | None
    prompt: PromptTemplate | None
    started_at: datetime
    finished_at: datetime
    latency_ms: int
    error_message: str | None = None

    @property
    def succeeded(self) -> bool:
        """Return whether the agent call itself succeeded."""

        return self.result is not None


class ReviewOrchestrator:
    """Coordinate provider-backed panel workers plus deterministic review rules."""

    def __init__(self, settings: Settings, provider: LLMProvider | None, store: SQLiteReviewStore) -> None:
        """Create the review pipeline with its provider and persistence store."""

        self._settings = settings
        self._provider = provider
        self._store = store
        self._agent_catalog = ScreeningAgentCatalog(provider, prompt_version=settings.prompt_version)

        # 保留这些私有字段，兼容现有测试与注入路径。
        self._precheck_agent = self._agent_catalog.precheck_agent
        self._evidence_agent = self._agent_catalog.evidence_agent
        self._value_agent = self._agent_catalog.value_agent
        self._meta_agent = self._agent_catalog.meta_agent

    @property
    def settings(self) -> Settings:
        """Expose resolved settings for runtime/service wiring without private-field reach-in."""

        return self._settings

    @property
    def provider(self) -> LLMProvider | None:
        """Expose the configured provider for runtime/service wiring."""

        return self._provider

    @property
    def store(self) -> SQLiteReviewStore:
        """Expose the persistence store for transport and runtime wiring."""

        return self._store

    @property
    def agent_catalog(self) -> ScreeningAgentCatalog:
        """Expose the built-in screening agent registry."""

        return self._agent_catalog

    def build_screening_workflow(self) -> ScreeningReviewWorkflow:
        """Build the workflow object that owns screening.review.v1 control flow."""

        return ScreeningReviewWorkflow(self)

    async def dry_run(self, manuscript: ManuscriptInput) -> DryRunOutput:
        """Run schema and deterministic precheck only, without any LLM calls."""

        venue_profile = self._resolve_venue_profile(manuscript)
        precheck = self._build_local_precheck(manuscript, venue_profile)
        self._store.save_event(
            run_id=None,
            event_type="dry_run_completed",
            level="INFO",
            created_at=datetime.now(timezone.utc).isoformat(),
            payload={
                "manuscript_id": manuscript.manuscript_id,
                "accepted_for_full_review": precheck.minimum_reviewable and not precheck.risk_flags,
            },
        )
        return DryRunOutput(
            manuscript_id=manuscript.manuscript_id,
            accepted_for_full_review=precheck.minimum_reviewable and not precheck.risk_flags,
            precheck=precheck,
            venue_profile=venue_profile,
        )

    async def review(self, manuscript: ManuscriptInput) -> ReviewOutput:
        """Run the built-in screening workflow and return the public review contract."""

        self.ensure_full_review_provider_available()
        run_id = str(uuid.uuid4())
        execution = await self.build_screening_workflow().execute(manuscript, run_id=run_id)
        return execution.review

    def ensure_full_review_provider_available(self) -> None:
        """Fail fast when a full review is requested without a real provider."""

        if self._provider is None:
            if self._settings.provider_backend == "mock":
                raise ProviderError(
                    "Configured mock backend is test-only without injected fixture responses. "
                    "Use dry-run, configure OpenAI, or inject a fixture-backed MockLLMProvider."
                )
            raise ProviderError(
                "Full screening review requires a configured LLM provider. Use /review/dry-run or configure "
                "OPENAI_API_KEY / GLORIOUS_MESS_OPENAI_API_KEY."
            )

    async def run_agent_node(
        self,
        *,
        run_id: str,
        manuscript: ManuscriptInput,
        node_id: str,
        venue_profile: VenueProfile,
        **extra_context: Any,
    ) -> AgentExecutionResult[Any]:
        """Execute one registered agent node with shared logging and prompt capture."""

        agent = self._agent_catalog.agent(node_id)
        spec = self._agent_catalog.spec(node_id)
        return await self._run_agent_with_logging(
            run_id=run_id,
            manuscript=manuscript,
            agent_name=spec.agent_name,
            agent_coro=agent.review(manuscript, venue_profile, **extra_context),
        )

    def _record_review_requested(
        self,
        *,
        run_id: str,
        manuscript: ManuscriptInput,
        venue_profile: VenueProfile,
    ) -> None:
        """Persist the review-request envelope before running any expensive steps."""

        self._store.save_event(
            run_id=run_id,
            event_type="review_requested",
            level="INFO",
            created_at=datetime.now(timezone.utc).isoformat(),
            payload={
                "manuscript_id": manuscript.manuscript_id,
                "title_preview": manuscript.title[:120],
                "provider_backend": self._settings.provider_backend,
                "resolved_venue_profile": venue_profile.model_dump(mode="json"),
            },
        )

    def _persist_review_projection(
        self,
        *,
        run_id: str,
        manuscript: ManuscriptInput,
        review: ReviewOutput,
    ) -> None:
        """Persist the final review projection and recommendation summary."""

        with self._store.transaction():
            self._store.save_review(run_id=run_id, request_payload=manuscript, review=review)
            self._store.save_event(
                run_id=run_id,
                event_type="recommendation_generated",
                level="INFO",
                created_at=datetime.now(timezone.utc).isoformat(),
                payload={
                    "manuscript_id": manuscript.manuscript_id,
                    "recommendation": review.final_recommendation.value,
                    "final_score": review.final_score,
                    "rule_hits": [item.code for item in review.rule_hits],
                },
            )
        LOGGER.info(
            "review_complete",
            extra={
                "event": "review_complete",
                "run_id": run_id,
                "status": "success",
                "details": {
                    "manuscript_id": manuscript.manuscript_id,
                    "recommendation": review.final_recommendation.value,
                    "final_score": review.final_score,
                },
            },
        )

    def _persist_risk_audit_projection(
        self,
        *,
        run_id: str,
        manuscript: ManuscriptInput,
        audit: RiskAuditOutput,
    ) -> None:
        """Persist a risk-audit summary event for workflow-native retrieval."""

        self._store.save_event(
            run_id=run_id,
            event_type="risk_audit_generated",
            level="INFO",
            created_at=datetime.now(timezone.utc).isoformat(),
            payload={
                "manuscript_id": manuscript.manuscript_id,
                "action": audit.action.value,
                "risk_flags": audit.risk_flags,
            },
        )
        LOGGER.info(
            "risk_audit_complete",
            extra={
                "event": "risk_audit_complete",
                "run_id": run_id,
                "status": "success",
                "details": {
                    "manuscript_id": manuscript.manuscript_id,
                    "action": audit.action.value,
                    "risk_flags": audit.risk_flags,
                },
            },
        )

    def _persist_venue_fit_projection(
        self,
        *,
        run_id: str,
        manuscript: ManuscriptInput,
        audit: VenueFitAuditOutput,
    ) -> None:
        """Persist a venue-fit summary event for workflow-native retrieval."""

        self._store.save_event(
            run_id=run_id,
            event_type="venue_fit_audit_generated",
            level="INFO",
            created_at=datetime.now(timezone.utc).isoformat(),
            payload={
                "manuscript_id": manuscript.manuscript_id,
                "action": audit.action.value,
                "venue_fit_score": audit.venue_fit_score,
                "meme_to_argument_score": audit.meme_to_argument_score,
            },
        )
        LOGGER.info(
            "venue_fit_audit_complete",
            extra={
                "event": "venue_fit_audit_complete",
                "run_id": run_id,
                "status": "success",
                "details": {
                    "manuscript_id": manuscript.manuscript_id,
                    "action": audit.action.value,
                    "venue_fit_score": audit.venue_fit_score,
                },
            },
        )

    def _build_local_precheck(
        self, manuscript: ManuscriptInput, venue_profile: VenueProfile
    ) -> PrecheckOutput:
        """Perform deterministic precheck so dry-run and degraded review remain available."""

        missing_sections: list[str] = []
        hard_failures: list[str] = []
        notes: list[str] = []
        risk_flags: list[str] = []

        title = manuscript.title.strip()
        abstract = manuscript.abstract.strip()
        body = manuscript.body.strip()

        if not title:
            missing_sections.append("title")
            hard_failures.append("missing_title")
        if not abstract:
            missing_sections.append("abstract")
            hard_failures.append("missing_abstract")
        if not body:
            missing_sections.append("body")
            hard_failures.append("missing_body")

        lowered_body = body.lower()
        reviewable_threshold = venue_profile.minimum_reviewable_characters or self._settings.minimum_reviewable_characters
        if body and len(body) < reviewable_threshold:
            hard_failures.append("body_too_short_for_review")
            notes.append(f"Body is below the minimum reviewable character threshold ({reviewable_threshold}).")

        for section in venue_profile.required_sections:
            if section in {"title", "abstract", "body"}:
                continue
            pattern = re.escape(section.lower())
            if not re.search(pattern, lowered_body):
                missing_sections.append(section)

        risky_markers = [
            ("risk_hate_or_harassment", r"\b(genocide|lynch|racial supremacy|ethnic cleansing)\b"),
            ("risk_dangerous_actionable", r"\b(build a bomb|doxx|swat)\b"),
            ("risk_self_harm", r"\b(suicide method|self-harm instructions)\b"),
            (
                "risk_illegal_evasion_or_fraud",
                r"\b(fake passport|counterfeit money|tax fraud|money laundering|forge documents|诈骗教程)\b",
            ),
            (
                "risk_exploitative_sexual_content",
                r"\b(revenge porn|偷拍|迷奸|rape guide|非自愿色情|sexual blackmail)\b",
            ),
        ]
        combined_text = f"{title}\n{abstract}\n{body}".lower()
        for flag, pattern in risky_markers:
            if re.search(pattern, combined_text):
                risk_flags.append(flag)
        weaponize_check_text = re.sub(
            r"\b(?:do not|don't|not to|avoid|avoids|warning against|warns(?: readers)? not to)\s+weaponiz(?:e|ing)\b",
            "",
            combined_text,
        )
        if re.search(r"\bweaponize\b", weaponize_check_text):
            risk_flags.append("risk_dangerous_actionable")

        minimum_reviewable = not hard_failures
        decision = self._normalize_precheck_decision(
            minimum_reviewable=minimum_reviewable,
            risk_flags=risk_flags,
        )

        return PrecheckOutput(
            decision=decision,
            minimum_reviewable=minimum_reviewable,
            hard_failures=sorted(set(hard_failures)),
            missing_sections=sorted(set(missing_sections)),
            risk_flags=sorted(set(risk_flags)),
            notes=notes,
        )

    def _merge_precheck(self, local: PrecheckOutput, llm: PrecheckOutput) -> PrecheckOutput:
        """Combine local hard guarantees with the richer LLM precheck notes."""

        hard_failures = sorted(set(local.hard_failures + llm.hard_failures))
        missing_sections = sorted(set(local.missing_sections + llm.missing_sections))
        risk_flags = sorted(set(local.risk_flags + llm.risk_flags))
        notes = local.notes + [item for item in llm.notes if item not in local.notes]
        minimum_reviewable = local.minimum_reviewable and llm.minimum_reviewable
        decision = self._normalize_precheck_decision(
            minimum_reviewable=minimum_reviewable,
            risk_flags=risk_flags,
        )
        return PrecheckOutput(
            decision=decision,
            minimum_reviewable=minimum_reviewable,
            hard_failures=hard_failures,
            missing_sections=missing_sections,
            risk_flags=risk_flags,
            notes=notes,
        )

    def _build_precheck_blocked_review(
        self,
        *,
        workflow_session_id: str,
        manuscript: ManuscriptInput,
        precheck: PrecheckOutput,
        venue_profile: VenueProfile,
        raw_agent_outputs: dict[str, RawAgentOutputEnvelope],
        agent_failures: list[AgentFailure],
    ) -> ReviewOutput:
        """Return a structured review even when the manuscript fails precheck."""

        gate_is_risk = bool(precheck.risk_flags)
        stop_reason = (
            "Risk flags require human review before downstream scoring."
            if gate_is_risk
            else "The manuscript did not clear minimum reviewability requirements."
        )
        required_revisions = [f"Fix precheck issue: {item}" for item in precheck.hard_failures]
        required_revisions.extend(f"Resolve or route risk flag: {item}" for item in precheck.risk_flags)
        blocked_scores = {
            dimension: ReviewDimensionScore(
                score=1 if dimension in {ReviewDimension.structural_integrity, ReviewDimension.core_claim_clarity, ReviewDimension.overall_merit} else 2,
                confidence=0.9,
                reason="Precheck gated full review, so this score reflects intake prerequisites rather than a full panel judgment.",
                supporting_evidence=[
                    build_evidence_item(
                        f"Hard failures: {', '.join(precheck.hard_failures) or 'none'}",
                        source_type=EvidenceSourceType.system,
                    )
                ],
                uncertainty_note="Downstream panel scoring was skipped because intake gates did not clear.",
            )
            for dimension in ReviewDimension
        }
        final_score = compute_weighted_final_score(blocked_scores, venue_profile)
        recommendation, recommendation_reason = compute_screening_recommendation(
            precheck=precheck,
            scores_by_dimension=blocked_scores,
            venue_profile=venue_profile,
            final_score=final_score,
        )
        return ReviewOutput(
            workflow_session_id=workflow_session_id,
            manuscript_id=manuscript.manuscript_id,
            resolved_venue_profile=venue_profile,
            paper_summary="Precheck gated the pipeline before a full content summary could be produced.",
            extracted_core_claim="unknown",
            scores_by_dimension=build_all_dimension_scores(blocked_scores),
            hard_failures=precheck.hard_failures,
            major_strengths=[],
            major_weaknesses=[stop_reason],
            required_revisions=required_revisions,
            optional_revisions=[f"Add missing section: {item}" for item in precheck.missing_sections if item not in {"title", "abstract", "body"}],
            risk_flags=precheck.risk_flags,
            rule_hits=[],
            agent_failures=agent_failures,
            final_score=final_score,
            final_recommendation=recommendation,
            final_rationale=f"Precheck blocked the manuscript. Recommendation basis: {recommendation_reason}",
            human_readable_review=(
                "The manuscript did not clear deterministic intake. Fix hard failures, add missing core sections, "
                "and route any risk flags to human review before requesting the next screening stage."
            ),
            community_facing_blurb="The screening desk did not advance this submission because intake gates did not clear.",
            raw_agent_outputs=raw_agent_outputs if self._settings.store_raw_agent_outputs else {},
        )

    def _resolve_venue_profile(self, manuscript: ManuscriptInput) -> VenueProfile:
        """Resolve a complete venue profile with explicit preset and threshold fields."""

        if manuscript.venue_profile is None:
            return VenueProfile.default_screening_profile(
                minimum_reviewable_characters=self._settings.minimum_reviewable_characters,
            )

        resolved_minimum = (
            manuscript.venue_profile.minimum_reviewable_characters
            or self._settings.minimum_reviewable_characters
        )
        return manuscript.venue_profile.model_copy(
            update={"minimum_reviewable_characters": resolved_minimum}
        )

    def _build_effective_precheck(
        self,
        *,
        precheck: PrecheckOutput,
        evidence_output: EvidenceAgentOutput | None,
        value_output: ValueAgentOutput | None,
        meta_output: FinalMetaReviewOutput,
    ) -> PrecheckOutput:
        """Merge downstream risk flags into the authoritative precheck state."""

        merged_risk_flags = self._merge_risk_flags(
            precheck=precheck,
            evidence_output=evidence_output,
            value_output=value_output,
            meta_output=meta_output,
        )
        return precheck.model_copy(
            update={
                "risk_flags": merged_risk_flags,
                "decision": self._normalize_precheck_decision(
                    minimum_reviewable=precheck.minimum_reviewable,
                    risk_flags=merged_risk_flags,
                ),
            }
        )

    def _build_final_review(
        self,
        *,
        workflow_session_id: str,
        manuscript: ManuscriptInput,
        venue_profile: VenueProfile,
        precheck: PrecheckOutput,
        effective_precheck: PrecheckOutput,
        meta_output: FinalMetaReviewOutput,
        raw_agent_outputs: dict[str, RawAgentOutputEnvelope],
        agent_failures: list[AgentFailure],
    ) -> ReviewOutput:
        """Project the final review from effective precheck plus meta-panel output."""

        updated_scores, rule_hits, rationale = apply_post_review_rules(
            precheck=effective_precheck,
            scores_by_dimension=meta_output.scores_by_dimension.as_dict(),
            venue_profile=venue_profile,
            meta_rationale=meta_output.final_rationale,
        )
        final_score = compute_weighted_final_score(updated_scores, venue_profile)
        recommendation, recommendation_reason = compute_screening_recommendation(
            precheck=effective_precheck,
            scores_by_dimension=updated_scores,
            venue_profile=venue_profile,
            final_score=final_score,
        )
        final_rationale = f"{rationale} Recommendation basis: {recommendation_reason}".strip()
        human_readable_review = self._render_human_readable_review(
            manuscript=manuscript,
            meta_output=meta_output,
            precheck=effective_precheck,
            recommendation=recommendation.value,
            recommendation_reason=recommendation_reason,
        )
        return ReviewOutput(
            workflow_session_id=workflow_session_id,
            manuscript_id=manuscript.manuscript_id,
            resolved_venue_profile=venue_profile,
            paper_summary=meta_output.paper_summary,
            extracted_core_claim=meta_output.extracted_core_claim,
            scores_by_dimension=build_all_dimension_scores(updated_scores),
            hard_failures=effective_precheck.hard_failures,
            major_strengths=meta_output.major_strengths,
            major_weaknesses=meta_output.major_weaknesses,
            required_revisions=meta_output.required_revisions,
            optional_revisions=meta_output.optional_revisions,
            risk_flags=effective_precheck.risk_flags,
            rule_hits=rule_hits,
            agent_failures=agent_failures,
            final_score=final_score,
            final_recommendation=recommendation,
            final_rationale=final_rationale,
            human_readable_review=human_readable_review,
            community_facing_blurb=meta_output.community_facing_blurb,
            raw_agent_outputs=raw_agent_outputs if self._settings.store_raw_agent_outputs else {},
        )

    def _build_risk_audit_output(
        self,
        *,
        workflow_session_id: str,
        manuscript: ManuscriptInput,
        venue_profile: VenueProfile,
        local_precheck: PrecheckOutput,
        llm_precheck: PrecheckOutput | None,
        effective_precheck: PrecheckOutput,
        raw_agent_outputs: dict[str, RawAgentOutputEnvelope],
    ) -> RiskAuditOutput:
        """Project the risk-audit workflow result into its public contract."""

        if effective_precheck.risk_flags:
            action = RiskAuditAction.FLAG_FOR_HUMAN_REVIEW
            rationale = "Risk flags were raised during intake, so a human risk review is required before any further screening."
        elif not effective_precheck.minimum_reviewable:
            action = RiskAuditAction.BLOCK_BEFORE_REVIEW
            rationale = "The manuscript failed basic intake requirements, so it should be repaired before continuing."
        else:
            action = RiskAuditAction.CLEAR
            rationale = "No blocking intake failures or risk flags were detected."

        return RiskAuditOutput(
            workflow_session_id=workflow_session_id,
            manuscript_id=manuscript.manuscript_id,
            resolved_venue_profile=venue_profile,
            local_precheck=local_precheck,
            llm_precheck=llm_precheck,
            effective_precheck=effective_precheck,
            risk_flags=effective_precheck.risk_flags,
            action=action,
            rationale=rationale,
            raw_agent_outputs=raw_agent_outputs if self._settings.store_raw_agent_outputs else {},
        )

    def _build_venue_fit_audit_output(
        self,
        *,
        workflow_session_id: str,
        manuscript: ManuscriptInput,
        venue_profile: VenueProfile,
        local_precheck: PrecheckOutput,
        llm_precheck: PrecheckOutput | None,
        effective_precheck: PrecheckOutput,
        value_review: ValueAgentOutput | None,
        raw_agent_outputs: dict[str, RawAgentOutputEnvelope],
    ) -> VenueFitAuditOutput:
        """Project the venue-fit workflow result into its public contract."""

        if effective_precheck.risk_flags:
            action = VenueFitAction.BLOCKED_BY_RISK
            rationale = "Risk flags mean venue fit should not be rewarded before a human safety review."
            venue_fit_score = 1
            meme_score = 1
            zhenghuo_score = 1
            strengths: list[str] = []
            weaknesses = ["Risk flags block any positive venue-fit judgment."]
        elif not effective_precheck.minimum_reviewable:
            action = VenueFitAction.INSUFFICIENT_FOR_FIT_JUDGMENT
            rationale = "The manuscript is too incomplete for a credible venue-fit judgment."
            venue_fit_score = 1
            meme_score = 1
            zhenghuo_score = 1
            strengths = []
            weaknesses = ["The submission did not clear minimum intake requirements."]
        elif value_review is None:
            action = VenueFitAction.BORDERLINE_FIT
            rationale = "The dedicated venue-fit panel was unavailable, so this result stays conservative."
            venue_fit_score = 2
            meme_score = 2
            zhenghuo_score = 2
            strengths = []
            weaknesses = ["Venue-fit panel output was missing, so the judgment is low confidence."]
        else:
            scores = value_review.dimension_scores
            venue_fit_score = scores.venue_fit.score
            meme_score = scores.meme_to_argument_conversion.score
            zhenghuo_score = scores.zhenghuo_execution.score
            discussion_score = scores.community_discussion_value.score
            strengths = value_review.major_strengths[:3]
            weaknesses = value_review.major_weaknesses[:3]
            if venue_fit_score >= 4 and meme_score >= 4 and zhenghuo_score >= 4 and discussion_score >= 3:
                action = VenueFitAction.STRONG_FIT
                rationale = "The manuscript feels venue-native: it has SHIT-compatible absurdity, disciplined zhenghuo execution, recognizable social bite, and solid meme-to-argument conversion."
            elif venue_fit_score >= 3 and zhenghuo_score >= 3:
                action = VenueFitAction.BORDERLINE_FIT
                rationale = "The manuscript has enough SHIT energy to stay in the conversation, but its conversion from bit to argument is not yet elite."
            else:
                action = VenueFitAction.MISALIGNED
                rationale = "The manuscript may have craft or effort, but it does not presently feel native to SHIT's absurd-academic venue logic."

        return VenueFitAuditOutput(
            workflow_session_id=workflow_session_id,
            manuscript_id=manuscript.manuscript_id,
            resolved_venue_profile=venue_profile,
            local_precheck=local_precheck,
            llm_precheck=llm_precheck,
            effective_precheck=effective_precheck,
            value_review=value_review,
            risk_flags=effective_precheck.risk_flags,
            venue_fit_score=venue_fit_score,
            meme_to_argument_score=meme_score,
            zhenghuo_execution_score=zhenghuo_score,
            action=action,
            rationale=rationale,
            top_strengths=strengths,
            top_weaknesses=weaknesses,
            raw_agent_outputs=raw_agent_outputs if self._settings.store_raw_agent_outputs else {},
        )

    @staticmethod
    def _merge_risk_flags(
        *,
        precheck: PrecheckOutput,
        evidence_output: EvidenceAgentOutput | None,
        value_output: ValueAgentOutput | None,
        meta_output: FinalMetaReviewOutput,
    ) -> list[str]:
        """Build the authoritative risk-flag set for final screening decisions."""

        combined = list(precheck.risk_flags)
        if evidence_output is not None:
            combined.extend(evidence_output.risk_flags)
        if value_output is not None:
            combined.extend(value_output.risk_flags)
        combined.extend(meta_output.risk_flags)
        return sorted(set(combined))

    @staticmethod
    def _build_raw_output(
        *,
        status: str,
        artifact_type: RawAgentArtifactType | None = None,
        payload: PrecheckOutput | EvidenceAgentOutput | ValueAgentOutput | FinalMetaReviewOutput | None = None,
    ) -> RawAgentOutputEnvelope:
        """Wrap raw agent payloads in a stable status-plus-payload envelope."""

        return RawAgentOutputEnvelope(status=status, artifact_type=artifact_type, payload=payload)

    @staticmethod
    def _normalize_precheck_decision(
        *,
        minimum_reviewable: bool,
        risk_flags: list[str],
    ) -> PrecheckDecision:
        """Normalize the precheck decision from merged facts, not stale upstream labels."""

        # 合并 precheck 时以最终事实字段重新归一化 decision，避免上游的 pass 在本地风险标记合入后变成陈旧状态。
        if risk_flags and not minimum_reviewable:
            return PrecheckDecision.REJECT
        if not minimum_reviewable or risk_flags:
            return PrecheckDecision.REVISION_REQUIRED
        return PrecheckDecision.PASS

    def _save_prompt_rendered_event(
        self,
        *,
        run_id: str,
        agent_name: str,
        prompt: PromptTemplate,
    ) -> None:
        """Persist prompt metadata so success and failure paths stay in sync."""

        self._store.save_event(
            run_id=run_id,
            event_type="prompt_rendered",
            level="DEBUG" if self._settings.log_prompt_text else "INFO",
            created_at=datetime.now(timezone.utc).isoformat(),
            payload={
                "agent_name": agent_name,
                "prompt_version": prompt.version,
                "prompt_hash": prompt.sha1,
                "prompt_text": prompt.content if self._settings.log_prompt_text else None,
            },
        )

    async def _run_agent_with_logging(
        self,
        *,
        run_id: str,
        manuscript: ManuscriptInput,
        agent_name: str,
        agent_coro: Awaitable[tuple[T, PromptTemplate]],
    ) -> AgentExecutionResult[T]:
        """Execute one agent, persist an execution log, and degrade only on agent/provider failure."""

        started = perf_counter()
        started_at = datetime.now(timezone.utc)
        prompt: PromptTemplate | None = None
        try:
            result, prompt = await agent_coro
            finished_at = datetime.now(timezone.utc)
            latency_ms = int((perf_counter() - started) * 1000)
            with self._store.transaction():
                self._save_prompt_rendered_event(run_id=run_id, agent_name=agent_name, prompt=prompt)
                self._store.save_agent_log(
                    AgentLogRecord(
                        run_id=run_id,
                        agent_name=agent_name,
                        status="success",
                        prompt_version=prompt.version,
                        prompt_hash=prompt.sha1,
                        latency_ms=latency_ms,
                        payload=result.model_dump(mode="json") if self._settings.store_raw_agent_outputs else None,
                    )
                )
            LOGGER.info(
                "agent_complete",
                extra={
                    "event": "agent_complete",
                    "run_id": run_id,
                    "agent_name": agent_name,
                    "prompt_version": prompt.version,
                    "status": "success",
                    "details": {"manuscript_id": manuscript.manuscript_id, "latency_ms": latency_ms},
                },
            )
            return AgentExecutionResult(
                result=result,
                prompt=prompt,
                started_at=started_at,
                finished_at=finished_at,
                latency_ms=latency_ms,
            )
        except AgentCallError as exc:
            finished_at = datetime.now(timezone.utc)
            latency_ms = int((perf_counter() - started) * 1000)
            prompt = exc.prompt
            error_message = str(exc.__cause__ or exc)
            with self._store.transaction():
                if prompt is not None:
                    self._save_prompt_rendered_event(run_id=run_id, agent_name=agent_name, prompt=prompt)
                self._store.save_agent_log(
                    AgentLogRecord(
                        run_id=run_id,
                        agent_name=agent_name,
                        status="failed",
                        prompt_version=prompt.version if prompt else "unknown",
                        prompt_hash=prompt.sha1 if prompt else "unknown",
                        latency_ms=latency_ms,
                        error_message=error_message,
                        payload=None,
                    )
                )
                self._store.save_retry_record(
                    run_id=run_id,
                    stage=agent_name,
                    reason=error_message,
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
                self._store.save_event(
                    run_id=run_id,
                    event_type="agent_failed",
                    level="WARNING",
                    created_at=datetime.now(timezone.utc).isoformat(),
                    payload={"agent_name": agent_name, "message": error_message},
                )
            LOGGER.warning(
                "agent_failed",
                extra={
                    "event": "agent_failed",
                    "run_id": run_id,
                    "agent_name": agent_name,
                    "status": "failed",
                    "details": {"manuscript_id": manuscript.manuscript_id, "error": error_message},
                },
            )
            return AgentExecutionResult(
                result=None,
                prompt=prompt,
                started_at=started_at,
                finished_at=finished_at,
                latency_ms=latency_ms,
                error_message=error_message,
            )

    def _render_human_readable_review(
        self,
        *,
        manuscript: ManuscriptInput,
        meta_output: FinalMetaReviewOutput,
        precheck: PrecheckOutput,
        recommendation: str,
        recommendation_reason: str,
    ) -> str:
        """Render a concise author-facing review note from the structured result."""

        required = "; ".join(meta_output.required_revisions[:3]) or "No blocking revisions listed."
        strengths = "; ".join(meta_output.major_strengths[:3]) or "No major strengths were recorded."
        weaknesses = "; ".join(meta_output.major_weaknesses[:3]) or "No major weaknesses were recorded."
        risk_flags = ", ".join(precheck.risk_flags + meta_output.risk_flags) or "none"
        return (
            f"Manuscript {manuscript.manuscript_id}: {meta_output.paper_summary}\n"
            f"Core claim: {meta_output.extracted_core_claim}\n"
            f"Screening decision: {recommendation}\n"
            f"Why: {recommendation_reason}\n"
            f"Strengths: {strengths}\n"
            f"Weaknesses: {weaknesses}\n"
            f"Required revisions: {required}\n"
            f"Risk flags: {risk_flags}"
        )
