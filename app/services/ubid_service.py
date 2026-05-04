from __future__ import annotations

from app.data.repository import DataRepository
from app.models.business import BusinessRecord
from app.models.resolution import (
    RecommendedAction,
    UBIDConfirmRequest,
    UBIDConfirmResponse,
    UBIDGenerateRequest,
    UBIDGenerateResponse,
)
from app.services.entity_resolution import EntityResolutionService


class UBIDService:
    def __init__(self, repository: DataRepository, resolution_service: EntityResolutionService):
        self.repository = repository
        self.resolution_service = resolution_service

    def generate(self, request: UBIDGenerateRequest) -> UBIDGenerateResponse:
        business_record = BusinessRecord(
            business_name=request.business_name,
            district=request.district,
            pin_code=request.pin_code,
            business_type=request.business_type,
            source=request.source or "USER_INTAKE",
            address=request.address,
            phone=request.phone,
            pan_hash=request.pan_hash,
            gstin_hash=request.gstin_hash,
        )
        resolution = self.resolution_service.resolve(business_record, limit=10)
        if resolution.candidate_matches and resolution.candidate_matches[0].decision.value == "AUTO_LINK":
            return UBIDGenerateResponse(
                ubid=resolution.candidate_matches[0].ubid,
                action=RecommendedAction.link_existing_ubid,
                needs_confirmation=True,
                confirmation_question=f"Existing UBID {resolution.candidate_matches[0].ubid} is a high-confidence match. Confirm linking instead of creating a new UBID?",
                resolution=resolution,
            )
        ubid = self._next_ubid(request.district, request.pin_code)
        action = resolution.recommended_action
        needs_confirmation = action != RecommendedAction.create_new_ubid
        question = resolution.confirmation_question
        if not needs_confirmation:
            question = f"No strong duplicate found. Create UBID {ubid} for this business?"
        return UBIDGenerateResponse(
            ubid=ubid,
            action=RecommendedAction.create_new_ubid if not needs_confirmation else action,
            needs_confirmation=True,
            confirmation_question=question,
            resolution=resolution,
        )

    def confirm(self, request: UBIDConfirmRequest) -> UBIDConfirmResponse:
        record = request.business_record.model_dump()
        if request.action == RecommendedAction.link_existing_ubid:
            if not request.candidate_ubid:
                raise ValueError("candidate_ubid is required for LINK_EXISTING_UBID")
            self.repository.record_confirmation(request.action.value, request.candidate_ubid, record)
            self.repository.add_source_link(request.candidate_ubid, record)
            return UBIDConfirmResponse(
                status="confirmed",
                action=request.action,
                ubid=request.candidate_ubid,
                message=f"Linked record to existing UBID {request.candidate_ubid}.",
            )
        if request.action == RecommendedAction.create_new_ubid:
            district = record.get("district") or "Unknown"
            pin_code = record.get("pin_code") or "000000"
            ubid = self._next_ubid(district, pin_code)
            self.repository.record_confirmation(request.action.value, ubid, record)
            self.repository.add_registry_entry(ubid, record)
            self.repository.add_source_link(ubid, record)
            return UBIDConfirmResponse(
                status="created",
                action=request.action,
                ubid=ubid,
                message=f"Created new UBID {ubid}.",
            )
        self.repository.record_confirmation(request.action.value, request.candidate_ubid, record)
        return UBIDConfirmResponse(
            status="queued",
            action=request.action,
            ubid=request.candidate_ubid,
            message="Record sent to human review queue.",
        )

    def _next_ubid(self, district: str, pin_code: str) -> str:
        district_code = self.repository.district_code_for(district)
        sequence = self.repository.registry_count() + 1
        return f"KA-{district_code}-{str(pin_code)[:6]}-{sequence:06d}"
