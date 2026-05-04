from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.models.resolution import (
    UBIDConfirmRequest,
    UBIDConfirmResponse,
    UBIDGenerateRequest,
    UBIDGenerateResponse,
)

router = APIRouter(prefix="/api/ubid", tags=["ubid"])


@router.post("/generate", response_model=UBIDGenerateResponse)
def generate_ubid(request: Request, payload: UBIDGenerateRequest) -> UBIDGenerateResponse:
    service = request.app.state.ubid_service
    return service.generate(payload)


@router.post("/confirm", response_model=UBIDConfirmResponse)
def confirm_ubid(request: Request, payload: UBIDConfirmRequest) -> UBIDConfirmResponse:
    service = request.app.state.ubid_service
    try:
        return service.confirm(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
