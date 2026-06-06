"""Workflow spec for a lightweight venue-fit audit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from glorious_mess_reviewer.runtime.registry import WorkflowSpec
from glorious_mess_reviewer.runtime.session import WorkflowExecutionResult, WorkflowRunContext
from glorious_mess_reviewer.schemas import (
    RawAgentArtifactType,
    RawAgentOutputEnvelope,
    VenueFitAuditOutput,
    WorkflowArtifactEnvelope,
    WorkflowArtifactType,
    WorkflowStepRecord,
    WorkflowStepStatus,
)

if TYPE_CHECKING:
    from glorious_mess_reviewer.orchestrator.review_pipeline import ReviewOrchestrator


@dataclass
class ScreeningVenueFitAuditExecution:
    """Workflow-level result before runtime persistence projection."""

    audit: VenueFitAuditOutput
    steps: list[WorkflowStepRecord]
    artifacts: dict[str, WorkflowArtifactEnvelope]

    def to_runtime_result(self) -> WorkflowExecutionResult:
        """Convert the venue-fit audit into runtime persistence payloads."""

        return WorkflowExecutionResult(
            final_output=self.audit.model_dump(mode="json"),
            steps=self.steps,
            artifacts=self.artifacts,
        )


class ScreeningVenueFitAuditWorkflow:
    """Own the venue-fit workflow that judges cultural alignment without full review."""

    workflow_id = "screening.venue_fit_audit.v1"
    node_sequence = (
        "resolve_venue",
        "precheck.local",
        "precheck.llm",
        "panel.value",
        "projection.venue_fit_audit",
    )

    def __init__(self, orchestrator: "ReviewOrchestrator") -> None:
        self._orchestrator = orchestrator

    async def execute(self, manuscript, *, run_id: str) -> ScreeningVenueFitAuditExecution:
        orchestrator = self._orchestrator
        orchestrator.ensure_full_review_provider_available()

        steps: list[WorkflowStepRecord] = []
        artifacts: dict[str, WorkflowArtifactEnvelope] = {}
        raw_agent_outputs: dict[str, RawAgentOutputEnvelope] = {}

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
                details={"preset_name": venue_profile.preset_name.value if venue_profile.preset_name else None},
            )
        )

        orchestrator._record_review_requested(run_id=run_id, manuscript=manuscript, venue_profile=venue_profile)

        local_started = datetime.now(timezone.utc)
        local_precheck = orchestrator._build_local_precheck(manuscript, venue_profile)
        local_finished = datetime.now(timezone.utc)
        artifacts["precheck.local"] = self._artifact(WorkflowArtifactType.precheck_output, local_precheck)
        steps.append(
            WorkflowStepRecord(
                node_id="precheck.local",
                status=WorkflowStepStatus.succeeded,
                started_at=local_started,
                finished_at=local_finished,
                details={"minimum_reviewable": local_precheck.minimum_reviewable, "risk_flags": len(local_precheck.risk_flags)},
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
        llm_precheck = precheck_call.result if precheck_call.succeeded else None
        effective_precheck = (
            orchestrator._merge_precheck(local_precheck, llm_precheck)
            if llm_precheck is not None
            else local_precheck
        )
        raw_agent_outputs[precheck_spec.agent_name] = orchestrator._build_raw_output(
            status="success" if llm_precheck is not None else "fallback",
            artifact_type=RawAgentArtifactType.precheck_output,
            payload=llm_precheck or local_precheck,
        )
        artifacts["precheck.llm"] = self._artifact(WorkflowArtifactType.agent_output, raw_agent_outputs[precheck_spec.agent_name])
        artifacts["precheck.effective"] = self._artifact(WorkflowArtifactType.precheck_output, effective_precheck)
        steps.append(
            WorkflowStepRecord(
                node_id="precheck.llm",
                status=WorkflowStepStatus.succeeded if precheck_call.succeeded else WorkflowStepStatus.failed,
                started_at=precheck_call.started_at,
                finished_at=precheck_call.finished_at,
                details={"agent": precheck_spec.agent_name, "latency_ms": precheck_call.latency_ms, "error": precheck_call.error_message},
            )
        )

        value_review = None
        value_spec = orchestrator.agent_catalog.spec("panel.value")
        if effective_precheck.minimum_reviewable and not effective_precheck.risk_flags:
            value_call = await orchestrator.run_agent_node(
                run_id=run_id,
                manuscript=manuscript,
                node_id="panel.value",
                venue_profile=venue_profile,
            )
            value_review = value_call.result if value_call.succeeded else None
            raw_agent_outputs[value_spec.agent_name] = orchestrator._build_raw_output(
                status="success" if value_review is not None else "failed",
                artifact_type=RawAgentArtifactType.value_output,
                payload=value_review,
            )
            artifacts["panel.value"] = self._artifact(
                WorkflowArtifactType.agent_output,
                raw_agent_outputs[value_spec.agent_name],
            )
            steps.append(
                WorkflowStepRecord(
                    node_id="panel.value",
                    status=WorkflowStepStatus.succeeded if value_call.succeeded else WorkflowStepStatus.failed,
                    started_at=value_call.started_at,
                    finished_at=value_call.finished_at,
                    details={"agent": value_spec.agent_name, "latency_ms": value_call.latency_ms, "error": value_call.error_message},
                )
            )
        else:
            now = datetime.now(timezone.utc)
            steps.append(
                WorkflowStepRecord(
                    node_id="panel.value",
                    status=WorkflowStepStatus.skipped,
                    started_at=now,
                    finished_at=now,
                    details={"reason": "precheck_not_clear_or_risk_flagged"},
                )
            )

        audit = orchestrator._build_venue_fit_audit_output(
            workflow_session_id=run_id,
            manuscript=manuscript,
            venue_profile=venue_profile,
            local_precheck=local_precheck,
            llm_precheck=llm_precheck,
            effective_precheck=effective_precheck,
            value_review=value_review,
            raw_agent_outputs=raw_agent_outputs,
        )
        orchestrator._persist_venue_fit_projection(run_id=run_id, manuscript=manuscript, audit=audit)
        steps.append(self._projection_step(audit))
        artifacts["decision.venue_fit_audit_output"] = self._artifact(
            WorkflowArtifactType.venue_fit_audit_output,
            audit,
        )
        return ScreeningVenueFitAuditExecution(audit=audit, steps=steps, artifacts=artifacts)

    @staticmethod
    def _artifact(artifact_type: WorkflowArtifactType, payload: object) -> WorkflowArtifactEnvelope:
        return WorkflowArtifactEnvelope(artifact_type=artifact_type, payload=payload)

    @staticmethod
    def _projection_step(audit: VenueFitAuditOutput) -> WorkflowStepRecord:
        now = datetime.now(timezone.utc)
        return WorkflowStepRecord(
            node_id="projection.venue_fit_audit",
            status=WorkflowStepStatus.succeeded,
            started_at=now,
            finished_at=now,
            details={
                "action": audit.action.value,
                "venue_fit_score": audit.venue_fit_score,
                "meme_to_argument_score": audit.meme_to_argument_score,
            },
        )


def build_screening_venue_fit_audit_workflow_spec(*, orchestrator: "ReviewOrchestrator") -> WorkflowSpec:
    """Build the runtime workflow spec for screening.venue_fit_audit.v1."""

    workflow = ScreeningVenueFitAuditWorkflow(orchestrator)

    async def runner(context: WorkflowRunContext) -> WorkflowExecutionResult:
        execution = await workflow.execute(context.request, run_id=context.session_id)
        return execution.to_runtime_result()

    return WorkflowSpec(
        workflow_id=workflow.workflow_id,
        description="Venue-fit audit that checks whether a manuscript feels native to SHIT before full review.",
        runner=runner,
        node_ids=workflow.node_sequence,
        edges=(
            ("resolve_venue", "precheck.local", None),
            ("precheck.local", "precheck.llm", None),
            ("precheck.llm", "panel.value", "reviewable_and_no_precheck_risk"),
            ("precheck.llm", "projection.venue_fit_audit", "precheck_blocked_or_risk_flagged"),
            ("panel.value", "projection.venue_fit_audit", None),
        ),
        artifact_keys=(
            "venue.resolved",
            "precheck.local",
            "precheck.llm",
            "precheck.effective",
            "panel.value",
            "decision.venue_fit_audit_output",
        ),
        tags=("screening", "venue-fit", "intake"),
    )
