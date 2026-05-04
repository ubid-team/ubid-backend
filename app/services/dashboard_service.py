from __future__ import annotations

from app.core.errors import ResourceNotFoundError
from app.data.repository import DataRepository
from app.models.dashboard import (
    DashboardProgress,
    DashboardResponse,
    ExplainabilityBlock,
    LinkedDepartmentRecord,
    RecentEvent,
)
from app.services.risk_service import RiskService


class DashboardService:
    def __init__(self, repository: DataRepository, risk_service: RiskService):
        self.repository = repository
        self.risk_service = risk_service

    def get_dashboard(self, ubid: str) -> DashboardResponse:
        registry = self.repository.find_registry_row(ubid)
        if not registry:
            raise ResourceNotFoundError(f"UBID {ubid} not found")
        dashboard_row = self.repository.find_dashboard_row(ubid) or {}
        risk = self.risk_service.calculate_for_ubid(ubid)
        links = self.repository.find_links(ubid)
        events = self.repository.find_events(ubid)[:10]

        linked_departments = [
            LinkedDepartmentRecord(
                department=row.get("source_system", ""),
                source_record_id=row.get("source_record_id", ""),
                status=registry.get("activity_status"),
                confidence=int(float(row.get("link_confidence", "0") or 0)),
            )
            for row in links
        ]
        recent_events = [
            RecentEvent(
                event_type=row.get("event_type", ""),
                department=row.get("source_system", ""),
                event_date=row.get("event_date", ""),
                severity=self._severity_for_event(row.get("event_outcome", "")),
            )
            for row in events
        ]
        human_review_required = str(dashboard_row.get("human_review_required", "")).lower() == "true"
        identity_reasons = [
            f"Registry contains {registry.get('source_record_count', '0')} linked source records.",
            f"Departments linked: {registry.get('linked_departments', 'unknown')}.",
        ]
        return DashboardResponse(
            ubid=ubid,
            business_name=registry.get("canonical_business_name", ""),
            status=registry.get("activity_status", "UNKNOWN"),
            district=registry.get("district"),
            pin_code=registry.get("pin_code"),
            risk_score=risk.risk_score,
            risk_level=risk.risk_level,
            progress=DashboardProgress(
                identity_verified=float(dashboard_row.get("progress_identity_verified_pct", "100") or 0) >= 75,
                department_records_linked=float(dashboard_row.get("progress_department_linkage_pct", "100") or 0) >= 75,
                compliance_checked=bool(recent_events),
                human_review_required=human_review_required,
            ),
            linked_departments=linked_departments,
            recent_events=recent_events,
            explainability=ExplainabilityBlock(
                risk_reasons=risk.reasons,
                identity_reasons=identity_reasons,
            ),
        )

    @staticmethod
    def _severity_for_event(outcome: str) -> str:
        outcome = (outcome or "").upper()
        if outcome in {"FAILED", "NOTICE"}:
            return "HIGH"
        if outcome in {"PENDING"}:
            return "MEDIUM"
        return "LOW"
