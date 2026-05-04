from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel


class ChatIntent(str, Enum):
    start_business = "START_BUSINESS"
    check_ubid = "CHECK_UBID"
    resolve_entity = "RESOLVE_ENTITY"
    dashboard_query = "DASHBOARD_QUERY"
    unknown = "UNKNOWN"


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    intent: ChatIntent
    structured_output: dict[str, Any]
    needs_confirmation: bool
    confirmation_question: str | None = None
    llm_used: bool
    fallback_used: bool
