from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.models.business import DataSourcesResponse, ReloadResponse

router = APIRouter(prefix="/api", tags=["data"])


@router.get("/data/sources", response_model=DataSourcesResponse)
def get_sources(request: Request) -> DataSourcesResponse:
    repository = request.app.state.repository
    return DataSourcesResponse(
        data_loaded=repository.data_loaded,
        source_count=len(repository.source_summaries()),
        loaded_sources=repository.source_summaries(),
    )


@router.post("/data/reload", response_model=ReloadResponse)
def reload_sources(request: Request) -> ReloadResponse:
    repository = request.app.state.repository
    repository.reload()
    return ReloadResponse(
        status="reloaded",
        data_loaded=repository.data_loaded,
        source_count=len(repository.source_summaries()),
        loaded_sources=repository.source_summaries(),
    )


@router.get("/business/search")
def search_businesses(request: Request, q: str = Query(..., min_length=1), limit: int = Query(20, ge=1, le=50)) -> dict[str, object]:
    repository = request.app.state.repository
    results = repository.search_businesses(q, limit)
    return {
        "query": q,
        "count": len(results),
        "results": [result.model_dump() for result in results],
    }
