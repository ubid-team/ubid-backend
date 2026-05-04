from __future__ import annotations

import re
from typing import Any

from app.data.repository import DataRepository
from app.models.business import BusinessRecord
from app.models.chat import ChatIntent, ChatResponse
from app.models.recommendations import BusinessRecommendationRequest
from app.services.dashboard_service import DashboardService
from app.services.entity_resolution import EntityResolutionService
from app.services.llm_service import LLMService
from app.services.recommendation_service import RecommendationService


class ChatService:
    def __init__(
        self,
        repository: DataRepository,
        resolution_service: EntityResolutionService,
        recommendation_service: RecommendationService,
        dashboard_service: DashboardService,
        llm_service: LLMService,
    ):
        self.repository = repository
        self.resolution_service = resolution_service
        self.recommendation_service = recommendation_service
        self.dashboard_service = dashboard_service
        self.llm_service = llm_service

    def chat(self, message: str, session_id: str | None = None) -> ChatResponse:
        intent = self._infer_intent(message)
        structured_output: dict[str, Any]
        needs_confirmation = False
        confirmation_question: str | None = None

        if intent == ChatIntent.start_business:
            recommendation = self.recommendation_service.recommend(self._build_recommendation_request(message))
            structured_output = recommendation.model_dump()
            structured_output["summary"] = "Business-start guidance prepared from deterministic recommendation rules."
        elif intent == ChatIntent.check_ubid:
            ubid = self._extract_ubid(message)
            dashboard = self.dashboard_service.get_dashboard(ubid)
            structured_output = dashboard.model_dump()
            structured_output["summary"] = f"Dashboard summary prepared for {ubid}."
        elif intent == ChatIntent.resolve_entity:
            business_record = self._build_business_record(message)
            resolution = self.resolution_service.resolve(business_record, limit=5)
            structured_output = resolution.model_dump()
            structured_output["summary"] = "Entity resolution completed from deterministic scoring."
            needs_confirmation = resolution.needs_confirmation
            confirmation_question = resolution.confirmation_question
        else:
            structured_output = {
                "summary": "I can help with business-start guidance, UBID lookups, and duplicate resolution when you provide business details.",
                "session_id": session_id,
            }

        reply, llm_used = self.llm_service.render_guidance(message, structured_output)
        return ChatResponse(
            reply=reply,
            intent=intent,
            structured_output=structured_output,
            needs_confirmation=needs_confirmation,
            confirmation_question=confirmation_question,
            llm_used=llm_used,
            fallback_used=not llm_used,
        )

    @staticmethod
    def _infer_intent(message: str) -> ChatIntent:
        lowered = message.lower()
        if "ubid" in lowered and re.search(r"ka-[a-z0-9-]+", lowered):
            return ChatIntent.check_ubid
        if any(token in lowered for token in ["start", "open", "setup", "new business", "employees"]):
            return ChatIntent.start_business
        if any(token in lowered for token in ["resolve", "duplicate", "same business", "gstin", "pan", "address"]):
            return ChatIntent.resolve_entity
        return ChatIntent.unknown

    @staticmethod
    def _extract_ubid(message: str) -> str:
        match = re.search(r"(KA-[A-Z0-9-]+)", message, flags=re.IGNORECASE)
        if not match:
            raise ValueError("No UBID found in message")
        return match.group(1).upper()

    @staticmethod
    def _build_recommendation_request(message: str) -> BusinessRecommendationRequest:
        lowered = message.lower()
        employees_match = re.search(r"(\d+)\s+employees?", lowered)
        business_type = "Food Processing" if "food" in lowered else "General Business"
        district = "Bengaluru Urban" if "bengaluru" in lowered or "bangalore" in lowered else None
        return BusinessRecommendationRequest(
            business_type=business_type,
            district=district,
            employees=int(employees_match.group(1)) if employees_match else None,
            uses_machinery="machinery" in lowered or "factory" in lowered or "processing" in lowered,
            handles_food="food" in lowered,
            pollution_category="orange" if "orange" in lowered else None,
        )

    @staticmethod
    def _build_business_record(message: str) -> BusinessRecord:
        pin_match = re.search(r"\b(\d{6})\b", message)
        return BusinessRecord(
            business_name=message[:120],
            address=message,
            pin_code=pin_match.group(1) if pin_match else None,
            source="USER_INTAKE",
        )
