"""Workflow spec for a lightweight risk-focused intake audit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from glorious_mess_reviewer.runtime.registry import WorkflowSpec
from glorious_mess_reviewer.runtime.session import WorkflowExecutionResult, WorkflowRunContext
from glorious_mess_reviewer.schemas import (
    RawAgentArtifactType,
    RawAgentOutputEnvelope,
    RiskAuditOutput,
    WorkflowArtifactEnvelope,
    WorkflowArtifactType,
    WorkflowStepRecord,
    WorkflowStepStatus,
)

if TYPE_CHECKING:
    from glorious_mess_reviewer.orchestrator.review_pipeline import ReviewOrchestrator


@dataclass
class ScreeningRiskAuditExecution:
    """Workflow-level result before runtime persistence projection."""

    audit: RiskAuditOutput
    steps: list[WorkflowStepRecord]
    artifacts: dict[str, WorkflowArtifactEnvelope]

    def to_runtime_result(self) -> WorkflowExecutionResult:
        """Convert the risk-audit result into runtime persistence payloads."""

        return WorkflowExecutionResult(
            final_output=self.audit.model_dump(mode="json"),
            steps=self.steps,
            artifacts=self.artifacts,
        )


class ScreeningRiskAuditWorkflow:
    """Own the risk-audit workflow that stops after precheck analysis."""

    workflow_id = "screening.risk_audit.v1"
    node_sequence = (
        "resolve_venue",
        "precheck.local",
        "precheck.llm",
        "projection.risk_audit",
    )

    def __init__(self, orchestrator: "ReviewOrchestrator") -> None:
        self._orchestrator = orchestrator

    async def execute(self, manuscript, *, run_id: str) -> ScreeningRiskAuditExecution:
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
                details={
                    "preset_name": venue_profile.preset_name.value if venue_profile.preset_name else None,
                },
            )
        )

        orchestrator._record_review_requested(
            run_id=run_id,
            manuscript=manuscript,
            venue_profile=venue_profile,
        )

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
                details={
                    "minimum_reviewable": local_precheck.minimum_reviewable,
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
        llm_precheck = precheck_call.result if precheck_call.succeeded else None
        effective_precheck = local_precheck
        if llm_precheck is not None:
            effective_precheck = orchestrator._merge_precheck(local_precheck, llm_precheck)
            raw_agent_outputs[precheck_spec.agent_name] = orchestrator._build_raw_output(
                status="success",
                artifact_type=RawAgentArtifactType.precheck_output,
                payload=llm_precheck,
            )
        else:
            raw_agent_outputs[precheck_spec.agent_name] = orchestrator._build_raw_output(
                status="fallback",
                artifact_type=RawAgentArtifactType.precheck_output,
                payload=local_precheck,
            )
        artifacts["precheck.llm"] = self._artifact(
            WorkflowArtifactType.agent_output,
            raw_agent_outputs[precheck_spec.agent_name],
        )
        artifacts["precheck.effective"] = self._artifact(WorkflowArtifactType.precheck_output, effective_precheck)
        steps.append(
            WorkflowStepRecord(
                node_id="precheck.llm",
                status=WorkflowStepStatus.succeeded if precheck_call.succeeded else WorkflowStepStatus.failed,
                started_at=precheck_call.started_at,
                finished_at=precheck_call.finished_at,
                details={
                    "agent": precheck_spec.agent_name,
                    "latency_ms": precheck_call.latency_ms,
                    "error": precheck_call.error_message,
                },
            )
        )

        audit = orchestrator._build_risk_audit_output(
            workflow_session_id=run_id,
            manuscript=manuscript,
            venue_profile=venue_profile,
            local_precheck=local_precheck,
            llm_precheck=llm_precheck,
            effective_precheck=effective_precheck,
            raw_agent_outputs=raw_agent_outputs,
        )
        orchestrator._persist_risk_audit_projection(run_id=run_id, manuscript=manuscript, audit=audit)
        steps.append(self._projection_step(audit))
        artifacts["decision.risk_audit_output"] = self._artifact(
            WorkflowArtifactType.risk_audit_output,
            audit,
        )
        return ScreeningRiskAuditExecution(audit=audit, steps=steps, artifacts=artifacts)

    @staticmethod
    def _artifact(artifact_type: WorkflowArtifactType, payload: object) -> WorkflowArtifactEnvelope:
        """Construct one typed workflow artifact envelope."""

        return WorkflowArtifactEnvelope(artifact_type=artifact_type, payload=payload)

    @staticmethod
    def _projection_step(audit: RiskAuditOutput) -> WorkflowStepRecord:
        """Build the final projection step for risk-audit results."""

        now = datetime.now(timezone.utc)
        return WorkflowStepRecord(
            node_id="projection.risk_audit",
            status=WorkflowStepStatus.succeeded,
            started_at=now,
            finished_at=now,
            details={
                "action": audit.action.value,
                "risk_flags": audit.risk_flags,
            },
        )


def build_screening_risk_audit_workflow_spec(*, orchestrator: "ReviewOrchestrator") -> WorkflowSpec:
    """Build the runtime workflow spec for screening.risk_audit.v1."""

    workflow = ScreeningRiskAuditWorkflow(orchestrator)

    async def runner(context: WorkflowRunContext) -> WorkflowExecutionResult:
        execution = await workflow.execute(context.request, run_id=context.session_id)
        return execution.to_runtime_result()

    return WorkflowSpec(
        workflow_id=workflow.workflow_id,
        description="Risk-focused intake audit that stops after local and LLM precheck analysis.",
        runner=runner,
        node_ids=workflow.node_sequence,
        edges=(
            ("resolve_venue", "precheck.local", None),
            ("precheck.local", "precheck.llm", None),
            ("precheck.llm", "projection.risk_audit", None),
        ),
        artifact_keys=(
            "venue.resolved",
            "precheck.local",
            "precheck.llm",
            "precheck.effective",
            "decision.risk_audit_output",
        ),
        tags=("screening", "risk-audit", "intake"),
    )
