from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.models.business import BusinessRecord


class MatchDecision(str, Enum):
    auto_link = "AUTO_LINK"
    human_review = "HUMAN_REVIEW"
    no_match = "NO_MATCH"


class RecommendedAction(str, Enum):
    link_existing_ubid = "LINK_EXISTING_UBID"
    create_new_ubid = "CREATE_NEW_UBID"
    send_to_human_review = "SEND_TO_HUMAN_REVIEW"


class MatchExplanation(BaseModel):
    name_score: int
    address_score: int
    pin_score: int
    phone_score: int
    pan_score: int
    gstin_score: int
    source_diversity_score: int
    evidence: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)


class CandidateMatch(BaseModel):
    ubid: str | None = None
    business_name: str
    source_record_id: str
    source: str
    match_score: int
    decision: MatchDecision
    explanation: MatchExplanation


class ResolveRequest(BaseModel):
    record: BusinessRecord
    limit: int = Field(default=10, ge=1, le=50)


class ResolveResponse(BaseModel):
    input_record: BusinessRecord
    candidate_matches: list[CandidateMatch]
    recommended_action: RecommendedAction
    needs_confirmation: bool
    confirmation_question: str | None = None


class UBIDGenerateRequest(BaseModel):
    business_name: str
    district: str
    pin_code: str
    business_type: str | None = None
    source: str | None = None
    address: str | None = None
    phone: str | None = None
    pan_hash: str | None = None
    gstin_hash: str | None = None


class UBIDGenerateResponse(BaseModel):
    ubid: str | None = None
    action: RecommendedAction
    needs_confirmation: bool
    confirmation_question: str | None = None
    resolution: ResolveResponse


class UBIDConfirmRequest(BaseModel):
    action: RecommendedAction
    candidate_ubid: str | None = None
    business_record: BusinessRecord


class UBIDConfirmResponse(BaseModel):
    status: str
    action: RecommendedAction
    ubid: str | None = None
    message: str
