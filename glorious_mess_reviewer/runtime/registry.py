"""Workflow registry primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from glorious_mess_reviewer.runtime.session import WorkflowExecutionResult, WorkflowRunContext

WorkflowRunner = Callable[[WorkflowRunContext], Awaitable[WorkflowExecutionResult]]


@dataclass(frozen=True)
class WorkflowSpec:
    """One named workflow plus its execution entrypoint."""

    workflow_id: str
    description: str
    runner: WorkflowRunner
    node_ids: tuple[str, ...] = ()
    edges: tuple[tuple[str, str, str | None], ...] = ()
    parallel_groups: tuple[tuple[str, ...], ...] = ()
    artifact_keys: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


class WorkflowRegistry:
    """In-memory registry for named workflow specs."""

    def __init__(self) -> None:
        self._workflows: dict[str, WorkflowSpec] = {}

    def register(self, workflow: WorkflowSpec) -> None:
        """Register a workflow spec under its stable identifier."""

        if workflow.workflow_id in self._workflows:
            raise ValueError(f"workflow '{workflow.workflow_id}' is already registered")
        self._workflows[workflow.workflow_id] = workflow

    def get(self, workflow_id: str) -> WorkflowSpec | None:
        """Return one registered workflow spec when present."""

        return self._workflows.get(workflow_id)

    def list_ids(self) -> list[str]:
        """Return registered workflow ids in sorted order."""

        return sorted(self._workflows.keys())

    def list_specs(self) -> tuple[WorkflowSpec, ...]:
        """Return registered specs in sorted identifier order."""

        return tuple(self._workflows[workflow_id] for workflow_id in self.list_ids())
