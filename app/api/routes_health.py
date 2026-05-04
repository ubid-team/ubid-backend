from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    repository = request.app.state.repository
    return {
        "status": "ok",
        "service": settings.service_name,
        "data_loaded": repository.data_loaded,
        "openrouter_configured": settings.openrouter_configured,
        "loaded_sources": [summary.logical_name for summary in repository.source_summaries()],
    }
