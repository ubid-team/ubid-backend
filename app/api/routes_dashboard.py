from __future__ import annotations

from fastapi import APIRouter, Request

from app.models.dashboard import DashboardResponse
from app.models.recommendations import BusinessRecommendationRequest, BusinessRecommendationResponse
from app.models.risk import RiskCalculateRequest, RiskCalculateResponse

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard/{ubid}", response_model=DashboardResponse)
def get_dashboard(request: Request, ubid: str) -> DashboardResponse:
    service = request.app.state.dashboard_service
    return service.get_dashboard(ubid)


@router.post("/risk/calculate", response_model=RiskCalculateResponse)
def calculate_risk(request: Request, payload: RiskCalculateRequest) -> RiskCalculateResponse:
    service = request.app.state.risk_service
    if payload.ubid:
        return service.calculate_for_ubid(payload.ubid)
    return service.calculate_for_record(payload.business_record)


@router.get("/recommendations/rules")
def get_recommendation_rules(request: Request) -> dict[str, object]:
    service = request.app.state.recommendation_service
    rules = service.get_rules()
    return {"count": len(rules), "rules": [rule.model_dump() for rule in rules]}


@router.post("/recommendations/business", response_model=BusinessRecommendationResponse)
def get_business_recommendations(
    request: Request,
    payload: BusinessRecommendationRequest,
) -> BusinessRecommendationResponse:
    service = request.app.state.recommendation_service
    return service.recommend(payload)
