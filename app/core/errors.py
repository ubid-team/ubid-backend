from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DataUnavailableError(RuntimeError):
    """Raised when the dataset is not loaded."""


class ResourceNotFoundError(RuntimeError):
    """Raised when a requested business resource is unavailable."""


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DataUnavailableError)
    async def handle_data_unavailable(_: Request, exc: DataUnavailableError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(ResourceNotFoundError)
    async def handle_not_found(_: Request, exc: ResourceNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})
