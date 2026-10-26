"""Application errors with safe, user-facing messages.

Every error that reaches the API is converted to:
    {"error": {"code": "...", "message": "..."}}
Internal details (paths, stack traces, raw provider payloads) are never returned.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("leaselens.errors")


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class UnsupportedFileError(AppError):
    status_code = 415
    code = "unsupported_file"


class FileTooLargeError(AppError):
    status_code = 413
    code = "file_too_large"


class ExtractionError(AppError):
    status_code = 422
    code = "extraction_failed"


class LimitExceededError(AppError):
    status_code = 413
    code = "limit_exceeded"


class CloudConsentRequiredError(AppError):
    status_code = 400
    code = "cloud_consent_required"


class ProviderError(AppError):
    """Base class for AI provider problems."""

    status_code = 503
    code = "provider_error"


class ProviderNotConfiguredError(ProviderError):
    status_code = 400
    code = "provider_not_configured"


class ProviderUnavailableError(ProviderError):
    status_code = 503
    code = "provider_unavailable"


class ModelNotFoundError(ProviderError):
    status_code = 503
    code = "model_not_found"


class ProviderResponseError(ProviderError):
    """The provider answered, but the answer could not be used."""

    status_code = 502
    code = "invalid_model_response"


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        logger.info("request failed code=%s status=%s", exc.code, exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Report which fields failed, never the submitted values (they may contain contract text).
        problems = []
        for err in exc.errors():
            location = ".".join(str(part) for part in err.get("loc", ()) if part != "body")
            problems.append(f"{location or 'request'}: {err.get('msg', 'invalid value')}")
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_request",
                    "message": "The request is not valid. " + "; ".join(problems[:5]),
                }
            },
        )

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.error("unexpected error type=%s", type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "Something went wrong on the server. Please try again.",
                }
            },
        )
