"""FastAPI application exposing review and venue endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import Depends, FastAPI, Query
from fastapi.responses import JSONResponse

from glorious_mess_reviewer.api.dependencies import get_app_reviewer, get_app_store
from glorious_mess_reviewer.api.errors import install_exception_handlers
from glorious_mess_reviewer.config import Settings, get_settings, setup_logging
from glorious_mess_reviewer.display import (
    build_fermentation_queue_overview,
    build_fermentation_queue_summaries,
    build_review_display,
)
from glorious_mess_reviewer.orchestrator import ReviewOrchestrator
from glorious_mess_reviewer.runtime import ReviewRuntimeService, build_review_service
from glorious_mess_reviewer.schemas import (
    DryRunOutput,
    ErrorResponse,
    HealthResponse,
    ManuscriptInput,
    PersistedReviewRecord,
    ReviewDisplayOutput,
    ReviewDisplayQueueOverview,
    ReviewDisplaySummary,
    ReviewOutput,
    ReviewRunSummary,
    RiskAuditOutput,
    VenueFitAuditOutput,
    VenuePresetName,
    VenueProfile,
    VenueValidationResponse,
    WorkflowInfo,
    WorkflowSessionRecord,
    WorkflowSessionStatus,
    WorkflowSessionSummary,
)
from glorious_mess_reviewer.storage import SQLiteReviewStore


def _build_review_service(
    settings: Settings,
    *,
    orchestrator: ReviewOrchestrator | None = None,
) -> ReviewRuntimeService:
    """Build an app-local review service from the resolved app settings."""

    # 应用实例统一持有自己的 review service，避免测试或嵌入调用误用全局缓存配置。
    return build_review_service(settings, orchestrator=orchestrator)


def create_app(
    *,
    settings: Settings | None = None,
    orchestrator: ReviewOrchestrator | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""

    resolved_settings = settings or get_settings()
    setup_logging(resolved_settings)

    app = FastAPI(
        title=resolved_settings.app_name,
        version="0.1.0",
        description="Venue-aware manuscript screening service with typed reviewer panels and rule grounding.",
    )
    install_exception_handlers(app)

    app.state.review_service = _build_review_service(resolved_settings, orchestrator=orchestrator)
    app.state.orchestrator = app.state.review_service.orchestrator

    @app.get("/health", response_model=HealthResponse, responses={500: {"model": ErrorResponse}})
    async def health_check() -> HealthResponse:
        review_service: ReviewRuntimeService = app.state.review_service
        return HealthResponse(
            status="ok",
            service=resolved_settings.app_name,
            provider_backend=resolved_settings.provider_backend,
            default_model=resolved_settings.default_model,
            database_ok=review_service.database_ok(),
            provider_configured=review_service.provider_configured(),
        )

    @app.post("/review", response_model=ReviewOutput, responses={422: {"model": ErrorResponse}})
    async def review_manuscript(
        manuscript: ManuscriptInput,
        reviewer: ReviewRuntimeService = Depends(get_app_reviewer),
    ) -> ReviewOutput:
        return await reviewer.review(manuscript)

    @app.post(
        "/review/risk-audit",
        response_model=RiskAuditOutput,
        responses={422: {"model": ErrorResponse}},
    )
    async def risk_audit_manuscript(
        manuscript: ManuscriptInput,
        reviewer: ReviewRuntimeService = Depends(get_app_reviewer),
    ) -> RiskAuditOutput:
        return await reviewer.risk_audit(manuscript)

    @app.post(
        "/review/venue-fit-audit",
        response_model=VenueFitAuditOutput,
        responses={422: {"model": ErrorResponse}},
    )
    async def venue_fit_audit_manuscript(
        manuscript: ManuscriptInput,
        reviewer: ReviewRuntimeService = Depends(get_app_reviewer),
    ) -> VenueFitAuditOutput:
        return await reviewer.venue_fit_audit(manuscript)

    @app.post(
        "/review/dry-run",
        response_model=DryRunOutput,
        responses={422: {"model": ErrorResponse}},
    )
    async def dry_run_review(
        manuscript: ManuscriptInput,
        reviewer: ReviewRuntimeService = Depends(get_app_reviewer),
    ) -> DryRunOutput:
        return await reviewer.dry_run(manuscript)

    @app.get(
        "/review/{run_id}",
        response_model=PersistedReviewRecord,
        responses={404: {"model": ErrorResponse}},
    )
    async def get_persisted_review(
        run_id: str,
        store: SQLiteReviewStore = Depends(get_app_store),
    ) -> PersistedReviewRecord | JSONResponse:
        persisted = store.get_review(run_id)
        if persisted is None:
            return JSONResponse(
                status_code=404,
                content=ErrorResponse(
                    error_code="review_not_found",
                    message=f"No persisted review found for run_id '{run_id}'.",
                ).model_dump(mode="json"),
            )
        return persisted

    @app.get(
        "/review/{run_id}/display",
        response_model=ReviewDisplayOutput,
        responses={404: {"model": ErrorResponse}},
    )
    async def get_review_display(
        run_id: str,
        store: SQLiteReviewStore = Depends(get_app_store),
    ) -> ReviewDisplayOutput | JSONResponse:
        persisted = store.get_review(run_id)
        if persisted is None:
            return JSONResponse(
                status_code=404,
                content=ErrorResponse(
                    error_code="review_not_found",
                    message=f"No persisted review found for run_id '{run_id}'.",
                ).model_dump(mode="json"),
            )
        return build_review_display(persisted)

    @app.get("/reviews", response_model=list[ReviewRunSummary])
    async def list_persisted_reviews(
        manuscript_id: str | None = None,
        limit: int = Query(default=20, ge=1, le=100),
        store: SQLiteReviewStore = Depends(get_app_store),
    ) -> list[ReviewRunSummary]:
        return store.list_reviews(manuscript_id=manuscript_id, limit=limit)

    @app.get("/reviews/display", response_model=list[ReviewDisplaySummary])
    async def list_review_display_summaries(
        manuscript_id: str | None = None,
        limit: int = Query(default=20, ge=1, le=100),
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
        | None = None,
        sort: Literal["created_at", "queue_priority", "repair_priority"] = "created_at",
        store: SQLiteReviewStore = Depends(get_app_store),
    ) -> list[ReviewDisplaySummary]:
        summaries = store.list_reviews(manuscript_id=manuscript_id, limit=100)
        records = [store.get_review(summary.run_id) for summary in summaries]
        return build_fermentation_queue_summaries(
            [record for record in records if record is not None],
            lane=lane,
            sort=sort,
            limit=limit,
        )

    @app.get("/reviews/display/overview", response_model=ReviewDisplayQueueOverview)
    async def get_review_display_queue_overview(
        manuscript_id: str | None = None,
        limit: int = Query(default=100, ge=1, le=100),
        store: SQLiteReviewStore = Depends(get_app_store),
    ) -> ReviewDisplayQueueOverview:
        summaries = store.list_reviews(manuscript_id=manuscript_id, limit=limit)
        records = [store.get_review(summary.run_id) for summary in summaries]
        return build_fermentation_queue_overview([record for record in records if record is not None])

    @app.get("/workflows", response_model=list[WorkflowInfo])
    async def list_registered_workflows(
        reviewer: ReviewRuntimeService = Depends(get_app_reviewer),
    ) -> list[WorkflowInfo]:
        return reviewer.list_workflows()

    @app.get("/workflow-sessions", response_model=list[WorkflowSessionSummary])
    async def list_persisted_workflow_sessions(
        workflow_id: str | None = None,
        manuscript_id: str | None = None,
        status: WorkflowSessionStatus | None = None,
        limit: int = Query(default=20, ge=1, le=100),
        reviewer: ReviewRuntimeService = Depends(get_app_reviewer),
    ) -> list[WorkflowSessionSummary]:
        return reviewer.list_workflow_sessions(
            workflow_id=workflow_id,
            manuscript_id=manuscript_id,
            status=status,
            limit=limit,
        )

    @app.get(
        "/workflow/{session_id}",
        response_model=WorkflowSessionRecord,
        responses={404: {"model": ErrorResponse}},
    )
    async def get_workflow_session(
        session_id: str,
        reviewer: ReviewRuntimeService = Depends(get_app_reviewer),
    ) -> WorkflowSessionRecord | JSONResponse:
        session = reviewer.get_workflow_session(session_id)
        if session is None:
            return JSONResponse(
                status_code=404,
                content=ErrorResponse(
                    error_code="workflow_not_found",
                    message=f"No persisted workflow session found for session_id '{session_id}'.",
                ).model_dump(mode="json"),
            )
        return session

    @app.get("/venue/default", response_model=VenueProfile)
    async def get_default_venue_profile(preset: VenuePresetName | None = None) -> VenueProfile:
        return VenueProfile.from_builtin_preset(
            preset,
            default_minimum_reviewable_characters=resolved_settings.minimum_reviewable_characters,
        )

    @app.post("/venue/validate", response_model=VenueValidationResponse)
    async def validate_venue_profile(venue_profile: VenueProfile) -> VenueValidationResponse:
        normalized = VenueProfile.model_validate(venue_profile.model_dump(mode="json"))
        return VenueValidationResponse(
            valid=True,
            venue_name=normalized.venue_name,
            normalized_profile=normalized,
        )

    return app
