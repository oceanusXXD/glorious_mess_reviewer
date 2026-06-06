"""FastAPI dependency helpers for application-scoped runtime objects."""

from __future__ import annotations

from fastapi import Request

from glorious_mess_reviewer.runtime import ReviewRuntimeService
from glorious_mess_reviewer.storage import SQLiteReviewStore


def get_app_reviewer(request: Request) -> ReviewRuntimeService:
    """Return the review service attached to the current FastAPI application state."""

    return request.app.state.review_service


def get_app_store(request: Request) -> SQLiteReviewStore:
    """Return the SQLite store attached to the current FastAPI application state."""

    return request.app.state.review_service.store
