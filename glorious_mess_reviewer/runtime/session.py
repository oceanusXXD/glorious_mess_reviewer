"""Runtime session context and workflow execution payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from glorious_mess_reviewer.config import Settings
from glorious_mess_reviewer.providers import LLMProvider
from glorious_mess_reviewer.schemas import ManuscriptInput, WorkflowArtifactEnvelope, WorkflowStepRecord
from glorious_mess_reviewer.storage import SQLiteReviewStore


@dataclass(frozen=True)
class WorkflowRunContext:
    """Execution-time context passed to one workflow runner."""

    session_id: str
    workflow_id: str
    request: ManuscriptInput
    settings: Settings
    provider: LLMProvider | None
    store: SQLiteReviewStore


@dataclass
class WorkflowExecutionResult:
    """In-memory execution result before persistence projection."""

    final_output: dict[str, Any]
    steps: list[WorkflowStepRecord]
    artifacts: dict[str, WorkflowArtifactEnvelope]
