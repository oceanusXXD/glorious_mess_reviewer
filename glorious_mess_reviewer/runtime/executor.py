"""Workflow runtime that executes registered workflow specs and persists traces."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from glorious_mess_reviewer.config import Settings
from glorious_mess_reviewer.providers import LLMProvider
from glorious_mess_reviewer.runtime.registry import WorkflowRegistry, WorkflowSpec
from glorious_mess_reviewer.runtime.session import WorkflowRunContext
from glorious_mess_reviewer.schemas import (
    ManuscriptInput,
    WorkflowArtifactRecord,
    WorkflowSessionRecord,
    WorkflowSessionStatus,
)
from glorious_mess_reviewer.storage import SQLiteReviewStore


class WorkflowRuntime:
    """Minimal workflow runtime for executing and persisting workflow sessions."""

    def __init__(
        self,
        *,
        settings: Settings,
        provider: LLMProvider | None,
        store: SQLiteReviewStore,
    ) -> None:
        self._settings = settings
        self._provider = provider
        self._store = store
        self._registry = WorkflowRegistry()

    def register_workflow(self, workflow: WorkflowSpec) -> None:
        """Register one executable workflow spec."""

        self._registry.register(workflow)

    def list_workflows(self) -> list[str]:
        """List all registered workflow identifiers."""

        return self._registry.list_ids()

    def list_workflow_specs(self) -> tuple[WorkflowSpec, ...]:
        """Expose registered workflow specs for diagnostics and tests."""

        return self._registry.list_specs()

    async def run_workflow(self, workflow_id: str, request: ManuscriptInput) -> WorkflowSessionRecord:
        """Execute one registered workflow and persist session/step/artifact rows."""

        workflow = self._registry.get(workflow_id)
        if workflow is None:
            raise ValueError(f"workflow '{workflow_id}' is not registered")

        now = datetime.now(timezone.utc)
        session = WorkflowSessionRecord(
            session_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            status=WorkflowSessionStatus.running,
            created_at=now,
            updated_at=now,
            request_payload=request.model_dump(mode="json"),
            final_output=None,
            steps=[],
            artifacts=[],
        )
        self._store.save_workflow_session(session)

        context = WorkflowRunContext(
            session_id=session.session_id,
            workflow_id=workflow_id,
            request=request,
            settings=self._settings,
            provider=self._provider,
            store=self._store,
        )

        try:
            execution = await workflow.runner(context)
        except Exception as exc:
            self._mark_workflow_failed(session=session, request=request, exc=exc)
            raise

        artifact_records: list[WorkflowArtifactRecord] = []
        try:
            with self._store.transaction():
                for step in execution.steps:
                    self._store.save_workflow_step(session_id=session.session_id, step=step)

                for artifact_key, payload in execution.artifacts.items():
                    artifact = WorkflowArtifactRecord(
                        artifact_key=artifact_key,
                        payload=payload,
                        created_at=datetime.now(timezone.utc),
                    )
                    artifact_records.append(artifact)
                    self._store.save_workflow_artifact(session_id=session.session_id, artifact=artifact)

                completed = session.model_copy(
                    update={
                        "status": WorkflowSessionStatus.completed,
                        "updated_at": datetime.now(timezone.utc),
                        "final_output": execution.final_output,
                        "steps": execution.steps,
                        "artifacts": artifact_records,
                    }
                )
                self._store.save_workflow_session(completed)
        except Exception as exc:
            self._mark_workflow_failed(session=session, request=request, exc=exc)
            raise

        return completed

    def _mark_workflow_failed(
        self,
        *,
        session: WorkflowSessionRecord,
        request: ManuscriptInput,
        exc: Exception,
    ) -> None:
        """Persist a failed workflow state and diagnostic event."""

        self._store.save_event(
            run_id=session.session_id,
            event_type="workflow_failed",
            level="ERROR",
            created_at=datetime.now(timezone.utc).isoformat(),
            payload={
                "session_id": session.session_id,
                "workflow_id": session.workflow_id,
                "manuscript_id": request.manuscript_id,
                "exception_type": exc.__class__.__name__,
                "message": str(exc),
            },
        )
        self._store.save_workflow_session(
            session.model_copy(
                update={
                    "status": WorkflowSessionStatus.failed,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
        )
