from __future__ import annotations

from pydantic import BaseModel, Field


class RecommendationRule(BaseModel):
    business_type: str
    required_registrations: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    primary_departments: list[str] = Field(default_factory=list)


class BusinessRecommendationRequest(BaseModel):
    business_type: str
    district: str | None = None
    employees: int | None = None
    uses_machinery: bool | None = None
    handles_food: bool | None = None
    pollution_category: str | None = None


class BusinessRecommendationResponse(BaseModel):
    recommended_departments: list[str]
    required_registrations: list[str]
    next_steps: list[str]
    risk_flags: list[str]
    explanation: list[str]
