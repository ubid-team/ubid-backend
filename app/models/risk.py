from __future__ import annotations

from pydantic import BaseModel, model_validator

from app.models.business import BusinessRecord


class RiskCalculateRequest(BaseModel):
    ubid: str | None = None
    business_record: BusinessRecord | None = None

    @model_validator(mode="after")
    def validate_input(self) -> "RiskCalculateRequest":
        if not self.ubid and not self.business_record:
            raise ValueError("Either ubid or business_record must be provided")
        return self


class RiskCalculateResponse(BaseModel):
    ubid: str | None = None
    risk_score: int
    risk_level: str
    reasons: list[str]
