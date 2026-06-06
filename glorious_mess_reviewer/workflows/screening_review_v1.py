"""Workflow spec for the built-in screening review flow."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from glorious_mess_reviewer.runtime.registry import WorkflowSpec
from glorious_mess_reviewer.runtime.session import WorkflowExecutionResult, WorkflowRunContext
from glorious_mess_reviewer.schemas import (
    AgentFailure,
    EvidenceAgentOutput,
    FinalMetaReviewOutput,
    ManuscriptInput,
    RawAgentArtifactType,
    RawAgentOutputEnvelope,
    ReviewOutput,
    RuleHitCollection,
    ValueAgentOutput,
    WorkflowArtifactEnvelope,
    WorkflowArtifactType,
    WorkflowStepRecord,
    WorkflowStepStatus,
)
from glorious_mess_reviewer.scoring import merge_sludge_panel_reviews

if TYPE_CHECKING:
    from glorious_mess_reviewer.orchestrator.review_pipeline import (
        AgentExecutionResult,
        ReviewOrchestrator,
    )


@dataclass
class ScreeningWorkflowExecution:
    """Workflow-level result before runtime persistence projection."""

    review: ReviewOutput
    steps: list[WorkflowStepRecord]
    artifacts: dict[str, WorkflowArtifactEnvelope]

    def to_runtime_result(self) -> WorkflowExecutionResult:
        """Convert the workflow result into the runtime execution payload."""

        return WorkflowExecutionResult(
            final_output=self.review.model_dump(mode="json"),
            steps=self.steps,
            artifacts=self.artifacts,
        )


class ScreeningReviewWorkflow:
    """Own the ordering, dependency rules, and artifacts for screening.review.v1."""

    workflow_id = "screening.review.v1"
    node_sequence = (
        "resolve_venue",
        "precheck.local",
        "precheck.llm",
        "panel.evidence",
        "panel.value",
        "panel.meta",
        "projection.review",
    )

    def __init__(self, orchestrator: "ReviewOrchestrator") -> None:
        self._orchestrator = orchestrator

    async def execute(self, manuscript: ManuscriptInput, *, run_id: str) -> ScreeningWorkflowExecution:
        orchestrator = self._orchestrator
        orchestrator.ensure_full_review_provider_available()
        steps: list[WorkflowStepRecord] = []
        artifacts: dict[str, WorkflowArtifactEnvelope] = {}
        raw_agent_outputs: dict[str, RawAgentOutputEnvelope] = {}
        agent_failures: list[AgentFailure] = []

        venue_started = datetime.now(timezone.utc)
        venue_profile = orchestrator._resolve_venue_profile(manuscript)
        venue_finished = datetime.now(timezone.utc)
        artifacts["venue.resolved"] = self._artifact(WorkflowArtifactType.venue_profile, venue_profile)
        steps.append(
            WorkflowStepRecord(
                node_id="resolve_venue",
                status=WorkflowStepStatus.succeeded,
                started_at=venue_started,
                finished_at=venue_finished,
                details={
                    "preset_name": venue_profile.preset_name.value if venue_profile.preset_name else None,
                    "minimum_reviewable_characters": venue_profile.minimum_reviewable_characters,
                },
            )
        )

        orchestrator._record_review_requested(
            run_id=run_id,
            manuscript=manuscript,
            venue_profile=venue_profile,
        )

        local_precheck_started = datetime.now(timezone.utc)
        local_precheck = orchestrator._build_local_precheck(manuscript, venue_profile)
        local_precheck_finished = datetime.now(timezone.utc)
        artifacts["precheck.local"] = self._artifact(WorkflowArtifactType.precheck_output, local_precheck)
        steps.append(
            WorkflowStepRecord(
                node_id="precheck.local",
                status=WorkflowStepStatus.succeeded,
                started_at=local_precheck_started,
                finished_at=local_precheck_finished,
                details={
                    "minimum_reviewable": local_precheck.minimum_reviewable,
                    "missing_sections": len(local_precheck.missing_sections),
                    "risk_flags": len(local_precheck.risk_flags),
                },
            )
        )

        precheck_call = await orchestrator.run_agent_node(
            run_id=run_id,
            manuscript=manuscript,
            node_id="precheck.llm",
            venue_profile=venue_profile,
            minimum_reviewable_characters=venue_profile.minimum_reviewable_characters,
        )
        precheck_spec = orchestrator.agent_catalog.spec("precheck.llm")
        precheck = local_precheck
        if precheck_call.succeeded and precheck_call.result is not None:
            precheck = orchestrator._merge_precheck(local_precheck, precheck_call.result)
            raw_agent_outputs[precheck_spec.agent_name] = orchestrator._build_raw_output(
                status="success",
                artifact_type=RawAgentArtifactType.precheck_output,
                payload=precheck_call.result,
            )
        else:
            raw_agent_outputs[precheck_spec.agent_name] = orchestrator._build_raw_output(
                status="fallback",
                artifact_type=RawAgentArtifactType.precheck_output,
                payload=local_precheck,
            )
            agent_failures.append(
                AgentFailure(
                    agent_name=precheck_spec.agent_name,
                    error_type="provider_degraded",
                    message="Used deterministic precheck fallback because the precheck panel failed.",
                )
            )
        artifacts["precheck.llm"] = self._artifact(WorkflowArtifactType.agent_output, raw_agent_outputs[precheck_spec.agent_name])
        artifacts["precheck.effective"] = self._artifact(WorkflowArtifactType.precheck_output, precheck)
        steps.append(self._agent_step_record(precheck_spec.node_id, precheck_call, agent_name=precheck_spec.agent_name))

        if not precheck.minimum_reviewable or precheck.risk_flags:
            gate_reason = "precheck_blocked" if not precheck.minimum_reviewable else "risk_gate"
            review = orchestrator._build_precheck_blocked_review(
                workflow_session_id=run_id,
                manuscript=manuscript,
                precheck=precheck,
                venue_profile=venue_profile,
                raw_agent_outputs=raw_agent_outputs,
                agent_failures=agent_failures,
            )
            orchestrator._persist_review_projection(run_id=run_id, manuscript=manuscript, review=review)
            steps.extend(self._skipped_downstream_steps(reason=gate_reason))
            steps.append(self._projection_step(review))
            artifacts["decision.rule_hits"] = self._artifact(
                WorkflowArtifactType.rule_trace,
                RuleHitCollection(items=[]),
            )
            artifacts["decision.review_output"] = self._artifact(WorkflowArtifactType.review_output, review)
            return ScreeningWorkflowExecution(review=review, steps=steps, artifacts=artifacts)

        evidence_task = orchestrator.run_agent_node(
            run_id=run_id,
            manuscript=manuscript,
            node_id="panel.evidence",
            venue_profile=venue_profile,
        )
        value_task = orchestrator.run_agent_node(
            run_id=run_id,
            manuscript=manuscript,
            node_id="panel.value",
            venue_profile=venue_profile,
        )
        evidence_call, value_call = await asyncio.gather(evidence_task, value_task)

        evidence_spec = orchestrator.agent_catalog.spec("panel.evidence")
        value_spec = orchestrator.agent_catalog.spec("panel.value")
        evidence_output = self._finalize_panel_result(
            orchestrator=orchestrator,
            call=evidence_call,
            spec=evidence_spec,
            raw_agent_outputs=raw_agent_outputs,
            agent_failures=agent_failures,
            failure_message="Evidence agent failed; proceeding with remaining signals.",
        )
        value_output = self._finalize_panel_result(
            orchestrator=orchestrator,
            call=value_call,
            spec=value_spec,
            raw_agent_outputs=raw_agent_outputs,
            agent_failures=agent_failures,
            failure_message="Value agent failed; proceeding with remaining signals.",
        )
        artifacts[evidence_spec.artifact_key] = self._artifact(
            WorkflowArtifactType.agent_output,
            raw_agent_outputs[evidence_spec.agent_name],
        )
        artifacts[value_spec.artifact_key] = self._artifact(
            WorkflowArtifactType.agent_output,
            raw_agent_outputs[value_spec.agent_name],
        )
        steps.append(self._agent_step_record(evidence_spec.node_id, evidence_call, agent_name=evidence_spec.agent_name))
        steps.append(self._agent_step_record(value_spec.node_id, value_call, agent_name=value_spec.agent_name))

        meta_spec = orchestrator.agent_catalog.spec("panel.meta")
        meta_output: FinalMetaReviewOutput
        if evidence_output is None and value_output is None:
            meta_output = merge_sludge_panel_reviews(evidence_output=None, value_output=None)
            raw_agent_outputs[meta_spec.agent_name] = orchestrator._build_raw_output(
                status="fallback",
                artifact_type=RawAgentArtifactType.meta_output,
                payload=meta_output,
            )
            agent_failures.append(
                AgentFailure(
                    agent_name=meta_spec.agent_name,
                    error_type="upstream_panel_missing",
                    message="Meta-review agent was skipped because all upstream panel agents failed; deterministic merge was used.",
                )
            )
            steps.append(
                WorkflowStepRecord(
                    node_id=meta_spec.node_id,
                    status=WorkflowStepStatus.skipped,
                    started_at=datetime.now(timezone.utc),
                    finished_at=datetime.now(timezone.utc),
                    details={
                        "agent": meta_spec.agent_name,
                        "reason": "no_surviving_panel_outputs",
                        "degraded": True,
                    },
                )
            )
        else:
            meta_call = await orchestrator.run_agent_node(
                run_id=run_id,
                manuscript=manuscript,
                node_id="panel.meta",
                venue_profile=venue_profile,
                precheck_json=json.dumps(precheck.model_dump(mode="json"), ensure_ascii=True, indent=2),
                evidence_json=json.dumps(
                    evidence_output.model_dump(mode="json") if evidence_output else {"status": "missing"},
                    ensure_ascii=True,
                    indent=2,
                ),
                value_json=json.dumps(
                    value_output.model_dump(mode="json") if value_output else {"status": "missing"},
                    ensure_ascii=True,
                    indent=2,
                ),
            )
            if meta_call.succeeded and meta_call.result is not None:
                meta_output = meta_call.result
                raw_agent_outputs[meta_spec.agent_name] = orchestrator._build_raw_output(
                    status="success",
                    artifact_type=RawAgentArtifactType.meta_output,
                    payload=meta_output,
                )
            else:
                meta_output = merge_sludge_panel_reviews(
                    evidence_output=evidence_output,
                    value_output=value_output,
                )
                raw_agent_outputs[meta_spec.agent_name] = orchestrator._build_raw_output(
                    status="fallback",
                    artifact_type=RawAgentArtifactType.meta_output,
                    payload=meta_output,
                )
                agent_failures.append(
                    AgentFailure(
                        agent_name=meta_spec.agent_name,
                        error_type="provider_degraded",
                        message="Meta-review agent failed; deterministic panel merge was used.",
                    )
                )
            steps.append(self._agent_step_record(meta_spec.node_id, meta_call, agent_name=meta_spec.agent_name))

        artifacts[meta_spec.artifact_key] = self._artifact(
            WorkflowArtifactType.agent_output,
            raw_agent_outputs[meta_spec.agent_name],
        )

        effective_precheck = orchestrator._build_effective_precheck(
            precheck=precheck,
            evidence_output=evidence_output,
            value_output=value_output,
            meta_output=meta_output,
        )
        artifacts["precheck.effective"] = self._artifact(WorkflowArtifactType.precheck_output, effective_precheck)

        review = orchestrator._build_final_review(
            workflow_session_id=run_id,
            manuscript=manuscript,
            venue_profile=venue_profile,
            precheck=precheck,
            effective_precheck=effective_precheck,
            meta_output=meta_output,
            raw_agent_outputs=raw_agent_outputs,
            agent_failures=agent_failures,
        )
        orchestrator._persist_review_projection(run_id=run_id, manuscript=manuscript, review=review)
        steps.append(self._projection_step(review))
        artifacts["decision.rule_hits"] = self._artifact(
            WorkflowArtifactType.rule_trace,
            RuleHitCollection(items=review.rule_hits),
        )
        artifacts["decision.review_output"] = self._artifact(WorkflowArtifactType.review_output, review)
        return ScreeningWorkflowExecution(review=review, steps=steps, artifacts=artifacts)

    @staticmethod
    def _artifact(artifact_type: WorkflowArtifactType, payload: object) -> WorkflowArtifactEnvelope:
        """Construct one typed workflow artifact envelope."""

        return WorkflowArtifactEnvelope(artifact_type=artifact_type, payload=payload)

    @staticmethod
    def _agent_step_record(
        node_id: str,
        call: "AgentExecutionResult[Any]",
        *,
        agent_name: str,
    ) -> WorkflowStepRecord:
        """Project one agent call into a workflow step record."""

        return WorkflowStepRecord(
            node_id=node_id,
            status=WorkflowStepStatus.succeeded if call.succeeded else WorkflowStepStatus.failed,
            started_at=call.started_at,
            finished_at=call.finished_at,
            details={
                "agent": agent_name,
                "latency_ms": call.latency_ms,
                "error": call.error_message,
            },
        )

    @staticmethod
    def _projection_step(review: ReviewOutput) -> WorkflowStepRecord:
        """Build the final projection step after review assembly."""

        now = datetime.now(timezone.utc)
        return WorkflowStepRecord(
            node_id="projection.review",
            status=WorkflowStepStatus.succeeded,
            started_at=now,
            finished_at=now,
            details={
                "recommendation": review.final_recommendation.value,
                "final_score": review.final_score,
                "rule_hits": [item.code for item in review.rule_hits],
            },
        )

    @staticmethod
    def _skipped_downstream_steps(*, reason: str) -> list[WorkflowStepRecord]:
        """Mark downstream panel nodes as skipped when precheck blocks review."""

        now = datetime.now(timezone.utc)
        return [
            WorkflowStepRecord(
                node_id=node_id,
                status=WorkflowStepStatus.skipped,
                started_at=now,
                finished_at=now,
                details={"reason": reason},
            )
            for node_id in ("panel.evidence", "panel.value", "panel.meta")
        ]

    @staticmethod
    def _finalize_panel_result(
        *,
        orchestrator: "ReviewOrchestrator",
        call: "AgentExecutionResult[Any]",
        spec,
        raw_agent_outputs: dict[str, RawAgentOutputEnvelope],
        agent_failures: list[AgentFailure],
        failure_message: str,
    ) -> EvidenceAgentOutput | ValueAgentOutput | None:
        """Update shared workflow state from one evidence/value panel call."""

        if call.succeeded and call.result is not None:
            artifact_type = (
                RawAgentArtifactType.evidence_output
                if spec.node_id == "panel.evidence"
                else RawAgentArtifactType.value_output
            )
            raw_agent_outputs[spec.agent_name] = orchestrator._build_raw_output(
                status="success",
                artifact_type=artifact_type,
                payload=call.result,
            )
            return call.result

        artifact_type = (
            RawAgentArtifactType.evidence_output
            if spec.node_id == "panel.evidence"
            else RawAgentArtifactType.value_output
        )
        raw_agent_outputs[spec.agent_name] = orchestrator._build_raw_output(
            status="failed",
            artifact_type=artifact_type,
        )
        agent_failures.append(
            AgentFailure(
                agent_name=spec.agent_name,
                error_type="provider_degraded",
                message=failure_message,
            )
        )
        return None


def build_screening_review_workflow_spec(*, orchestrator: "ReviewOrchestrator") -> WorkflowSpec:
    """Build the runtime workflow spec for screening.review.v1."""

    workflow = ScreeningReviewWorkflow(orchestrator)

    async def runner(context: WorkflowRunContext) -> WorkflowExecutionResult:
        execution = await workflow.execute(context.request, run_id=context.session_id)
        return execution.to_runtime_result()

    return WorkflowSpec(
        workflow_id=workflow.workflow_id,
        description="Venue-aware initial screening workflow for S.H.I.T-style tracks.",
        runner=runner,
        node_ids=workflow.node_sequence,
        edges=(
            ("resolve_venue", "precheck.local", None),
            ("precheck.local", "precheck.llm", None),
            ("precheck.llm", "panel.evidence", "reviewable_and_no_precheck_risk"),
            ("precheck.llm", "panel.value", "reviewable_and_no_precheck_risk"),
            ("precheck.llm", "projection.review", "precheck_blocked_or_risk_flagged"),
            ("panel.evidence", "panel.meta", "at_least_one_panel_available"),
            ("panel.value", "panel.meta", "at_least_one_panel_available"),
            ("panel.meta", "projection.review", None),
        ),
        parallel_groups=(("panel.evidence", "panel.value"),),
        artifact_keys=(
            "venue.resolved",
            "precheck.local",
            "precheck.llm",
            "precheck.effective",
            "panel.evidence",
            "panel.value",
            "panel.meta",
            "decision.rule_hits",
            "decision.review_output",
        ),
        tags=("screening", "review", "venue-aware", "workflow"),
    )
