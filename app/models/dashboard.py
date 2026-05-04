from __future__ import annotations

from pydantic import BaseModel, Field


class DashboardProgress(BaseModel):
    identity_verified: bool
    department_records_linked: bool
    compliance_checked: bool
    human_review_required: bool


class LinkedDepartmentRecord(BaseModel):
    department: str
    source_record_id: str
    status: str | None = None
    confidence: int


class RecentEvent(BaseModel):
    event_type: str
    department: str
    event_date: str
    severity: str


class ExplainabilityBlock(BaseModel):
    risk_reasons: list[str] = Field(default_factory=list)
    identity_reasons: list[str] = Field(default_factory=list)


class DashboardResponse(BaseModel):
    ubid: str
    business_name: str
    status: str
    district: str | None = None
    pin_code: str | None = None
    risk_score: int
    risk_level: str
    progress: DashboardProgress
    linked_departments: list[LinkedDepartmentRecord]
    recent_events: list[RecentEvent]
    explainability: ExplainabilityBlock
