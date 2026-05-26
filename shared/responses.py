from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from starlette.exceptions import HTTPException as StarletteHTTPException


def success_response(obj: Any = None) -> dict[str, Any]:
    return {"success": True, "payload": obj if obj is not None else {}}


def error_response(obj: Any = None) -> dict[str, Any]:
    return {"success": False, "error": obj if obj is not None else {}}


def json_safe(obj: Any) -> Any:
    return jsonable_encoder(
        obj,
        custom_encoder={
            bytes: lambda value: f"<{len(value)} bytes>",
        },
    )


def validation_errors_safe(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe_errors = []

    for error in errors:
        safe_error = dict(error)

        if "input" in safe_error:
            safe_error["input"] = str(safe_error["input"])

        safe_errors.append(safe_error)

    return safe_errors


def install_response_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response({"detail": json_safe(exc.detail)}),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=error_response({"detail": json_safe(validation_errors_safe(exc.errors()))}),
        )
