from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.config import settings
from backend.responses import error_response


ERROR_CODES_BY_STATUS = {
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_request: Request, exc: RequestValidationError):
        details = [
            {
                "field": ".".join(str(part) for part in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_response(
                "VALIDATION_ERROR", "Request validation failed", details=details
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_request: Request, exc: StarletteHTTPException):
        code = ERROR_CODES_BY_STATUS.get(
            exc.status_code,
            "INTERNAL_ERROR" if exc.status_code >= 500 else "BAD_REQUEST",
        )
        message = (
            str(exc.detail) if exc.status_code < 500 else "An internal error occurred"
        )
        return JSONResponse(
            status_code=exc.status_code, content=error_response(code, message)
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_request: Request, exc: Exception):
        if not settings.is_production:
            print(f"Unhandled application error: {exc!r}")
        return JSONResponse(
            status_code=500,
            content=error_response("INTERNAL_ERROR", "An internal error occurred"),
        )
