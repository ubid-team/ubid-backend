from __future__ import annotations

from fastapi import APIRouter, Request

from app.models.resolution import ResolveRequest, ResolveResponse

router = APIRouter(prefix="/api", tags=["resolution"])


@router.post("/resolve", response_model=ResolveResponse)
def resolve_entity(request: Request, payload: ResolveRequest) -> ResolveResponse:
    service = request.app.state.entity_resolution_service
    return service.resolve(payload.record, payload.limit)
