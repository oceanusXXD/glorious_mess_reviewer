"""SQLite persistence for review records and execution logs."""

from __future__ import annotations

from contextlib import contextmanager
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from threading import local

from glorious_mess_reviewer.schemas.contracts import (
    AgentLogRecord,
    ManuscriptInput,
    PersistedReviewRecord,
    ReviewOutput,
    ReviewRunSummary,
    VenueProfile,
    WorkflowArtifactEnvelope,
    WorkflowArtifactRecord,
    WorkflowSessionRecord,
    WorkflowSessionSummary,
    WorkflowSessionStatus,
    WorkflowStepRecord,
    WorkflowStepStatus,
)


class SQLiteReviewStore:
    """Persist review outputs and subagent execution logs in SQLite."""

    def __init__(self, database_path: Path) -> None:
        """Open a SQLite-backed repository and initialize tables."""

        self._database_path = Path(database_path)
        self._transaction_state = local()
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection_scope(self):
        """Reuse the active transaction connection when one exists."""

        active_connection = getattr(self._transaction_state, "connection", None)
        if active_connection is not None:
            yield active_connection
            return

        with self._connect() as connection:
            yield connection

    @contextmanager
    def transaction(self):
        """Group multiple store operations into one SQLite transaction."""

        active_connection = getattr(self._transaction_state, "connection", None)
        if active_connection is not None:
            yield
            return

        connection = self._connect()
        self._transaction_state.connection = connection
        try:
            with connection:
                yield
        finally:
            self._transaction_state.connection = None
            connection.close()

    def _init_db(self) -> None:
        with self._connect() as connection:
            # review_runs 保存最终审稿结果；其余表分别记录 agent、重试和事件流。
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS review_runs (
                    run_id TEXT PRIMARY KEY,
                    manuscript_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    request_payload_json TEXT NOT NULL,
                    review_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS event_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    event_type TEXT NOT NULL,
                    level TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    prompt_hash TEXT NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    error_message TEXT,
                    payload_json TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS retry_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_sessions (
                    session_id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    manuscript_id TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    request_payload_json TEXT NOT NULL,
                    final_output_json TEXT
                )
                """
            )
            self._ensure_workflow_sessions_manuscript_id(connection)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    details_json TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    artifact_key TEXT NOT NULL,
                    artifact_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT OR REPLACE INTO schema_metadata (key, value) VALUES (?, ?)",
                ("schema_version", "2"),
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_review_runs_manuscript_created
                ON review_runs (manuscript_id, created_at DESC)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_event_logs_run_type
                ON event_logs (run_id, event_type, id DESC)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_workflow_sessions_browse
                ON workflow_sessions (workflow_id, status, manuscript_id, updated_at DESC)
                """
            )

    @staticmethod
    def _workflow_session_manuscript_id(session: WorkflowSessionRecord) -> str:
        """Return the indexed manuscript identifier stored beside the workflow payload."""

        manuscript_id = session.request_payload.get("manuscript_id", "")
        return str(manuscript_id).strip()

    @staticmethod
    def _ensure_workflow_sessions_manuscript_id(connection: sqlite3.Connection) -> None:
        """Add and backfill the workflow-session manuscript id column for older local databases."""

        columns = {
            row["name"] if isinstance(row, sqlite3.Row) else row[1]
            for row in connection.execute("PRAGMA table_info(workflow_sessions)").fetchall()
        }
        if "manuscript_id" in columns:
            return

        connection.execute("ALTER TABLE workflow_sessions ADD COLUMN manuscript_id TEXT")
        rows = connection.execute(
            "SELECT session_id, request_payload_json FROM workflow_sessions WHERE manuscript_id IS NULL"
        ).fetchall()
        for row in rows:
            payload_json = row["request_payload_json"] if isinstance(row, sqlite3.Row) else row[1]
            session_id = row["session_id"] if isinstance(row, sqlite3.Row) else row[0]
            try:
                payload = json.loads(payload_json)
            except (TypeError, json.JSONDecodeError):
                payload = {}
            manuscript_id = str(payload.get("manuscript_id", "")).strip()
            connection.execute(
                "UPDATE workflow_sessions SET manuscript_id = ? WHERE session_id = ?",
                (manuscript_id, session_id),
            )

    def save_review(self, *, run_id: str, request_payload: ManuscriptInput, review: ReviewOutput) -> None:
        """Persist the final review and its originating request."""

        with self._connection_scope() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO review_runs (run_id, manuscript_id, created_at, request_payload_json, review_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    review.manuscript_id,
                    review.created_at.isoformat(),
                    json.dumps(request_payload.model_dump(mode="json"), ensure_ascii=True),
                    json.dumps(review.model_dump(mode="json"), ensure_ascii=True),
                ),
            )

    def save_workflow_session(self, session: WorkflowSessionRecord) -> None:
        """Persist or update one workflow session envelope."""

        with self._connection_scope() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO workflow_sessions (
                    session_id,
                    workflow_id,
                    manuscript_id,
                    status,
                    created_at,
                    updated_at,
                    request_payload_json,
                    final_output_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    session.workflow_id,
                    self._workflow_session_manuscript_id(session),
                    session.status.value,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                    json.dumps(session.request_payload, ensure_ascii=True),
                    json.dumps(session.final_output, ensure_ascii=True)
                    if session.final_output is not None
                    else None,
                ),
            )

    def save_workflow_step(self, *, session_id: str, step: WorkflowStepRecord) -> None:
        """Persist one workflow step execution row."""

        with self._connection_scope() as connection:
            connection.execute(
                """
                INSERT INTO workflow_steps (
                    session_id,
                    node_id,
                    status,
                    started_at,
                    finished_at,
                    details_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    step.node_id,
                    step.status.value,
                    step.started_at.isoformat(),
                    step.finished_at.isoformat(),
                    json.dumps(step.details, ensure_ascii=True) if step.details is not None else None,
                ),
            )

    def save_workflow_artifact(self, *, session_id: str, artifact: WorkflowArtifactRecord) -> None:
        """Persist one workflow artifact row."""

        with self._connection_scope() as connection:
            connection.execute(
                """
                INSERT INTO workflow_artifacts (
                    session_id,
                    artifact_key,
                    artifact_json,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    session_id,
                    artifact.artifact_key,
                    json.dumps(artifact.payload.model_dump(mode="json"), ensure_ascii=True),
                    artifact.created_at.isoformat(),
                ),
            )

    def get_workflow_session(self, session_id: str) -> WorkflowSessionRecord | None:
        """Load one workflow session with its steps and artifacts."""

        with self._connection_scope() as connection:
            row = connection.execute(
                """
                SELECT
                    session_id,
                    workflow_id,
                    status,
                    created_at,
                    updated_at,
                    request_payload_json,
                    final_output_json
                FROM workflow_sessions
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
            if row is None:
                return None

            step_rows = connection.execute(
                """
                SELECT
                    node_id,
                    status,
                    started_at,
                    finished_at,
                    details_json
                FROM workflow_steps
                WHERE session_id = ?
                ORDER BY id
                """,
                (session_id,),
            ).fetchall()
            artifact_rows = connection.execute(
                """
                SELECT
                    artifact_key,
                    artifact_json,
                    created_at
                FROM workflow_artifacts
                WHERE session_id = ?
                ORDER BY id
                """,
                (session_id,),
            ).fetchall()

        steps = [
            WorkflowStepRecord(
                node_id=item["node_id"],
                status=WorkflowStepStatus(item["status"]),
                started_at=datetime.fromisoformat(item["started_at"]),
                finished_at=datetime.fromisoformat(item["finished_at"]),
                details=json.loads(item["details_json"]) if item["details_json"] is not None else None,
            )
            for item in step_rows
        ]
        artifacts = [
            WorkflowArtifactRecord(
                artifact_key=item["artifact_key"],
                payload=WorkflowArtifactEnvelope.model_validate(json.loads(item["artifact_json"])),
                created_at=datetime.fromisoformat(item["created_at"]),
            )
            for item in artifact_rows
        ]

        return WorkflowSessionRecord(
            session_id=row["session_id"],
            workflow_id=row["workflow_id"],
            status=WorkflowSessionStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            request_payload=json.loads(row["request_payload_json"]),
            final_output=json.loads(row["final_output_json"]) if row["final_output_json"] else None,
            steps=steps,
            artifacts=artifacts,
        )

    def list_workflow_sessions(
        self,
        *,
        workflow_id: str | None = None,
        manuscript_id: str | None = None,
        status: WorkflowSessionStatus | str | None = None,
        limit: int = 20,
    ) -> list[WorkflowSessionSummary]:
        """Return persisted workflow-session summaries ordered from newest to oldest."""

        normalized_limit = max(1, min(limit, 100))
        status_value = status.value if isinstance(status, WorkflowSessionStatus) else status
        query = (
            "SELECT session_id, workflow_id, manuscript_id, status, created_at, updated_at, request_payload_json, final_output_json "
            "FROM workflow_sessions "
            "WHERE (? IS NULL OR workflow_id = ?) "
            "AND (? IS NULL OR status = ?) "
            "AND (? IS NULL OR manuscript_id = ?) "
            "ORDER BY updated_at DESC "
            "LIMIT ?"
        )

        summaries: list[WorkflowSessionSummary] = []
        with self._connection_scope() as connection:
            rows = connection.execute(
                query,
                (
                    workflow_id,
                    workflow_id,
                    status_value,
                    status_value,
                    manuscript_id,
                    manuscript_id,
                    normalized_limit,
                ),
            ).fetchall()
            for row in rows:
                request_payload = json.loads(row["request_payload_json"])
                row_manuscript_id = row["manuscript_id"] or str(request_payload.get("manuscript_id", ""))

                final_output = json.loads(row["final_output_json"]) if row["final_output_json"] else None
                summaries.append(
                    WorkflowSessionSummary(
                        session_id=row["session_id"],
                        workflow_id=row["workflow_id"],
                        status=WorkflowSessionStatus(row["status"]),
                        manuscript_id=row_manuscript_id,
                        created_at=datetime.fromisoformat(row["created_at"]),
                        updated_at=datetime.fromisoformat(row["updated_at"]),
                        final_output_type=_workflow_final_output_type(row["workflow_id"], final_output),
                    )
                )

        return summaries

    def get_review(self, run_id: str) -> PersistedReviewRecord | None:
        """Load one persisted review by run identifier."""

        with self._connection_scope() as connection:
            row = connection.execute(
                "SELECT run_id, request_payload_json, review_json FROM review_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()

            if row is None:
                return None

            request_payload = ManuscriptInput.model_validate(json.loads(row["request_payload_json"]))
            review_payload = self._normalized_review_payload(
                connection=connection,
                run_id=row["run_id"],
                request_payload=request_payload,
                review_payload=json.loads(row["review_json"]),
            )

        return PersistedReviewRecord(
            run_id=row["run_id"],
            request_payload=request_payload,
            review=ReviewOutput.model_validate(review_payload),
        )

    def list_reviews(
        self,
        *,
        manuscript_id: str | None = None,
        limit: int = 20,
    ) -> list[ReviewRunSummary]:
        """Return persisted review summaries ordered from newest to oldest."""

        normalized_limit = max(1, min(limit, 100))
        query = (
            "SELECT run_id, manuscript_id, created_at, request_payload_json, review_json "
            "FROM review_runs "
            "WHERE (? IS NULL OR manuscript_id = ?) "
            "ORDER BY created_at DESC "
            "LIMIT ?"
        )

        summaries: list[ReviewRunSummary] = []
        with self._connection_scope() as connection:
            rows = connection.execute(query, (manuscript_id, manuscript_id, normalized_limit)).fetchall()
            for row in rows:
                review_payload = json.loads(row["review_json"])
                resolved_venue_profile = self._resolved_venue_profile_payload(
                    connection=connection,
                    run_id=row["run_id"],
                    request_payload=None,
                    request_payload_json=row["request_payload_json"],
                    review_payload=review_payload,
                )
                summaries.append(
                    ReviewRunSummary(
                        run_id=row["run_id"],
                        manuscript_id=row["manuscript_id"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        final_score=review_payload["final_score"],
                        final_recommendation=review_payload["final_recommendation"],
                        resolved_venue_profile=resolved_venue_profile,
                    )
                )
        return summaries

    def _normalized_review_payload(
        self,
        *,
        connection: sqlite3.Connection,
        run_id: str,
        request_payload: ManuscriptInput,
        review_payload: dict[str, object],
    ) -> dict[str, object]:
        """Backfill newer required review fields for legacy persisted rows."""

        if (
            review_payload.get("resolved_venue_profile") is not None
            and review_payload.get("workflow_session_id") is not None
        ):
            return review_payload

        normalized = dict(review_payload)
        if normalized.get("resolved_venue_profile") is None:
            normalized["resolved_venue_profile"] = self._resolved_venue_profile_payload(
                connection=connection,
                run_id=run_id,
                request_payload=request_payload.model_dump(mode="json"),
                request_payload_json=None,
                review_payload=review_payload,
            )
        normalized.setdefault("workflow_session_id", run_id)
        return normalized

    def _resolved_venue_profile_payload(
        self,
        *,
        connection: sqlite3.Connection,
        run_id: str,
        request_payload: dict[str, object] | None,
        request_payload_json: str | None,
        review_payload: dict[str, object],
    ) -> dict[str, object]:
        """Resolve the venue profile payload needed for summary and full review reconstruction."""

        resolved_venue_profile = review_payload.get("resolved_venue_profile")
        if resolved_venue_profile is not None:
            return resolved_venue_profile

        event_row = connection.execute(
            "SELECT payload_json FROM event_logs WHERE run_id = ? AND event_type = 'review_requested' ORDER BY id DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        if event_row is not None and event_row["payload_json"]:
            event_payload = json.loads(event_row["payload_json"])
            event_profile = event_payload.get("resolved_venue_profile")
            if event_profile is not None:
                return event_profile

        if request_payload is None and request_payload_json is not None:
            request_payload = json.loads(request_payload_json)

        request_profile = request_payload.get("venue_profile") if request_payload is not None else None
        if request_profile is not None:
            return request_profile

        return VenueProfile.default_screening_profile().model_dump(mode="json")

    def save_agent_log(self, record: AgentLogRecord) -> None:
        """Persist one subagent execution record."""

        with self._connection_scope() as connection:
            connection.execute(
                """
                INSERT INTO agent_runs (run_id, agent_name, status, prompt_version, prompt_hash, latency_ms, error_message, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.run_id,
                    record.agent_name,
                    record.status,
                    record.prompt_version,
                    record.prompt_hash,
                    record.latency_ms,
                    record.error_message,
                    json.dumps(record.payload, ensure_ascii=True) if record.payload is not None else None,
                ),
            )

    def save_retry_record(self, *, run_id: str, stage: str, reason: str, created_at: str) -> None:
        """Persist a degraded-stage retry or fallback notice."""

        with self._connection_scope() as connection:
            connection.execute(
                """
                INSERT INTO retry_records (run_id, stage, reason, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, stage, reason, created_at),
            )

    def save_event(
        self,
        *,
        run_id: str | None,
        event_type: str,
        level: str,
        created_at: str,
        payload: dict[str, object] | None = None,
    ) -> None:
        """Persist request, rule, and recommendation events for observability."""

        with self._connection_scope() as connection:
            connection.execute(
                """
                INSERT INTO event_logs (run_id, event_type, level, created_at, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    event_type,
                    level,
                    created_at,
                    json.dumps(payload, ensure_ascii=True) if payload is not None else None,
                ),
            )

    def healthcheck(self) -> bool:
        """Return whether the SQLite database can answer a trivial query."""

        try:
            with self._connect() as connection:
                connection.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False


def _workflow_final_output_type(workflow_id: str, final_output: dict[str, object] | None) -> str | None:
    """Infer the public final-output model for a persisted workflow session."""

    if final_output is None:
        return None
    if workflow_id == "screening.review.v1":
        return "review_output"
    if workflow_id == "screening.risk_audit.v1":
        return "risk_audit_output"
    if workflow_id == "screening.venue_fit_audit.v1":
        return "venue_fit_audit_output"
    return "unknown"
