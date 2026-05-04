from __future__ import annotations

from fastapi import APIRouter, Request

from app.models.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: Request, payload: ChatRequest) -> ChatResponse:
    service = request.app.state.chat_service
    return service.chat(payload.message, payload.session_id)
