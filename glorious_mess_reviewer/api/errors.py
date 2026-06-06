"""Shared API exception helpers and handlers."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from glorious_mess_reviewer.providers import ProviderError
from glorious_mess_reviewer.schemas import ErrorResponse

LOGGER = logging.getLogger(__name__)


def install_exception_handlers(app: FastAPI) -> None:
    """Register consistent error responses on the FastAPI app."""

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        LOGGER.warning(
            "invalid_request",
            extra={
                "event": "invalid_request",
                "status": "failed",
                "details": {
                    "method": request.method,
                    "path": str(request.url.path),
                    "error_count": len(exc.errors()),
                },
            },
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=ErrorResponse(
                error_code="invalid_request",
                message="Request schema validation failed.",
                details={"errors": exc.errors()},
            ).model_dump(mode="json"),
        )

    @app.exception_handler(ProviderError)
    async def handle_provider_error(request: Request, exc: ProviderError) -> JSONResponse:
        LOGGER.warning(
            "provider_failure",
            extra={
                "event": "provider_failure",
                "status": "failed",
                "details": {
                    "method": request.method,
                    "path": str(request.url.path),
                    "error": str(exc),
                    "exception_type": exc.__class__.__name__,
                },
            },
        )
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=ErrorResponse(
                error_code="provider_failure",
                message=str(exc),
            ).model_dump(mode="json"),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # 兜底异常必须先记录，再返回统一错误结构，方便线上排查。
        LOGGER.exception(
            "unhandled_api_exception",
            extra={
                "event": "unhandled_api_exception",
                "status": "failed",
                "details": {"path": str(request.url.path), "exception_type": exc.__class__.__name__},
            },
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error_code="internal_error",
                message="Unexpected server failure.",
                details={"type": exc.__class__.__name__},
            ).model_dump(mode="json"),
        )
