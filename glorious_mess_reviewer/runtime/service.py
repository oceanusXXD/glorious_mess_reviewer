"""Application-facing review service built on top of the workflow runtime."""

from __future__ import annotations

from glorious_mess_reviewer.config import Settings
from glorious_mess_reviewer.orchestrator import ReviewOrchestrator
from glorious_mess_reviewer.providers import LLMProvider
from glorious_mess_reviewer.runtime.executor import WorkflowRuntime
from glorious_mess_reviewer.schemas import (
    DryRunOutput,
    ManuscriptInput,
    ReviewOutput,
    RiskAuditOutput,
    VenueFitAuditOutput,
    WorkflowEdge,
    WorkflowInfo,
    WorkflowSessionRecord,
    WorkflowSessionStatus,
    WorkflowSessionSummary,
)
from glorious_mess_reviewer.storage import SQLiteReviewStore


class ReviewRuntimeService:
    """Application-facing service exposing dry-run and runtime-backed full review."""

    def __init__(
        self,
        *,
        settings: Settings,
        provider: LLMProvider | None,
        store: SQLiteReviewStore,
        orchestrator: ReviewOrchestrator,
        runtime: WorkflowRuntime,
    ) -> None:
        self._settings = settings
        self._provider = provider
        self._store = store
        self._orchestrator = orchestrator
        self._runtime = runtime

    @property
    def orchestrator(self) -> ReviewOrchestrator:
        """Return the compatibility orchestrator used by the service."""

        return self._orchestrator

    @property
    def store(self) -> SQLiteReviewStore:
        """Return the persistence store used by the service."""

        return self._store

    def database_ok(self) -> bool:
        """Return whether the backing SQLite store is healthy."""

        return self._store.healthcheck()

    def provider_configured(self) -> bool:
        """Return whether a provider is available for full review."""

        return self._provider is not None

    async def dry_run(self, manuscript: ManuscriptInput) -> DryRunOutput:
        """Run deterministic precheck only."""

        return await self._orchestrator.dry_run(manuscript)

    async def review(self, manuscript: ManuscriptInput) -> ReviewOutput:
        """Run the named screening workflow and return the public review contract."""

        session = await self._runtime.run_workflow("screening.review.v1", manuscript)
        if session.final_output is None:
            raise RuntimeError("screening.review.v1 completed without a final output payload")
        return ReviewOutput.model_validate(session.final_output)

    async def risk_audit(self, manuscript: ManuscriptInput) -> RiskAuditOutput:
        """Run the risk-audit workflow and return its public contract."""

        session = await self._runtime.run_workflow("screening.risk_audit.v1", manuscript)
        if session.final_output is None:
            raise RuntimeError("screening.risk_audit.v1 completed without a final output payload")
        return RiskAuditOutput.model_validate(session.final_output)

    async def venue_fit_audit(self, manuscript: ManuscriptInput) -> VenueFitAuditOutput:
        """Run the venue-fit workflow and return its public contract."""

        session = await self._runtime.run_workflow("screening.venue_fit_audit.v1", manuscript)
        if session.final_output is None:
            raise RuntimeError("screening.venue_fit_audit.v1 completed without a final output payload")
        return VenueFitAuditOutput.model_validate(session.final_output)

    def list_workflows(self) -> list[WorkflowInfo]:
        """Return registered workflow metadata for API and CLI discovery."""

        return [
            WorkflowInfo(
                workflow_id=spec.workflow_id,
                description=spec.description,
                node_ids=list(spec.node_ids),
                edges=[
                    WorkflowEdge(source=source, target=target, condition=condition)
                    for source, target, condition in spec.edges
                ],
                parallel_groups=[list(group) for group in spec.parallel_groups],
                artifact_keys=list(spec.artifact_keys),
                tags=list(spec.tags),
            )
            for spec in self._runtime.list_workflow_specs()
        ]

    def get_workflow_session(self, session_id: str) -> WorkflowSessionRecord | None:
        """Load one persisted workflow session by id."""

        return self._store.get_workflow_session(session_id)

    def list_workflow_sessions(
        self,
        *,
        workflow_id: str | None = None,
        manuscript_id: str | None = None,
        status: WorkflowSessionStatus | None = None,
        limit: int = 20,
    ) -> list[WorkflowSessionSummary]:
        """Return persisted workflow-session summaries for operator browsing."""

        return self._store.list_workflow_sessions(
            workflow_id=workflow_id,
            manuscript_id=manuscript_id,
            status=status,
            limit=limit,
        )
