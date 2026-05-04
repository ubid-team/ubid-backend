from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.data.repository import DataRepository
from app.models.business import BusinessRecord
from app.models.risk import RiskCalculateResponse
from app.utils.scoring import clamp
from app.utils.text import contains_any


class RiskService:
    def __init__(self, repository: DataRepository):
        self.repository = repository

    def calculate_for_ubid(self, ubid: str) -> RiskCalculateResponse:
        registry = self.repository.find_registry_row(ubid) or {}
        linked_records = self.repository.find_source_master_by_ubid(ubid)
        events = self.repository.find_events(ubid)
        linked_departments = {row.get("source_system", "") for row in linked_records if row.get("source_system")}
        business_type = registry.get("business_type", "")
        activity_status = (registry.get("activity_status", "") or "").upper()
        pollution_category = next((row.get("pollution_category", "") for row in linked_records if row.get("pollution_category")), "")
        last_activity_date = registry.get("last_activity_date") or next(
            (row.get("last_event_date", "") for row in linked_records if row.get("last_event_date")),
            "",
        )
        score = 0
        reasons: list[str] = []

        if not linked_departments:
            score += 25
            reasons.append("No department records are linked to this UBID")

        if self._expects_department(business_type, "FACTORY") and "FACTORY" not in linked_departments:
            score += 15
            reasons.append("Factories Act record is missing for a machinery-intensive business")
        if self._expects_department(business_type, "KSPCB") and "KSPCB" not in linked_departments:
            score += 15
            reasons.append("KSPCB consent record is missing for a pollution-sensitive business")
        if "GST" not in linked_departments:
            score += 10
            reasons.append("No linked GST taxpayer record found")

        months_since_activity = self._months_since(last_activity_date)
        if months_since_activity is not None and months_since_activity >= 24:
            score += 25
            reasons.append("No inspection or compliance activity for more than 24 months")
        elif months_since_activity is not None and months_since_activity >= 12:
            score += 15
            reasons.append("No inspection or compliance activity for more than 12 months")

        if activity_status in {"CLOSED", "EXPIRED"}:
            score += 25
            reasons.append("Business status is closed or expired")
        elif activity_status == "DORMANT":
            score += 15
            reasons.append("Business status is dormant")

        if pollution_category.lower() in {"red", "orange"}:
            score += 15 if pollution_category.lower() == "red" else 10
            reasons.append(f"KSPCB pollution category is {pollution_category.lower()}")

        if any(event.get("event_outcome", "").upper() in {"PENDING", "NOTICE", "FAILED"} for event in events):
            score += 10
            reasons.append("Recent compliance events contain pending or adverse outcomes")

        risk_score = clamp(score)
        return RiskCalculateResponse(
            ubid=ubid,
            risk_score=risk_score,
            risk_level=self._risk_level(risk_score),
            reasons=reasons,
        )

    def calculate_for_record(self, record: BusinessRecord) -> RiskCalculateResponse:
        score = 0
        reasons: list[str] = []
        if not record.pan_hash:
            score += 10
            reasons.append("PAN hash is missing")
        if not record.gstin_hash:
            score += 10
            reasons.append("GSTIN hash is missing")
        if contains_any(record.business_type or "", ["food", "processing", "manufacturing"]):
            score += 10
            reasons.append("Business type usually requires stronger compliance linkage")
        if record.uses_machinery:
            score += 15
            reasons.append("Machinery usage increases compliance dependency on Factories and safety records")
        if record.handles_food:
            score += 10
            reasons.append("Food handling increases licensing and inspection requirements")
        if (record.pollution_category or "").lower() in {"red", "orange"}:
            score += 15 if record.pollution_category.lower() == "red" else 10
            reasons.append(f"Pollution category {record.pollution_category.lower()} carries elevated regulatory risk")
        if not record.phone:
            score += 5
            reasons.append("Phone contact is missing")
        if not record.pin_code:
            score += 5
            reasons.append("PIN code is missing")
        risk_score = clamp(score)
        return RiskCalculateResponse(
            ubid=None,
            risk_score=risk_score,
            risk_level=self._risk_level(risk_score),
            reasons=reasons,
        )

    @staticmethod
    def _months_since(value: str | None) -> int | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value)).replace(tzinfo=UTC)
        except ValueError:
            try:
                parsed = datetime.strptime(str(value), "%Y-%m-%d").replace(tzinfo=UTC)
            except ValueError:
                return None
        now = datetime.now(UTC)
        return (now.year - parsed.year) * 12 + (now.month - parsed.month)

    @staticmethod
    def _expects_department(business_type: str, department: str) -> bool:
        business_type = (business_type or "").lower()
        if department == "FACTORY":
            return contains_any(business_type, ["manufacturing", "plastic", "mould", "factory", "engineering", "processing"])
        if department == "KSPCB":
            return contains_any(business_type, ["manufacturing", "processing", "textile", "chemical", "mould", "food"])
        return False

    @staticmethod
    def _risk_level(score: int) -> str:
        if score >= 85:
            return "CRITICAL"
        if score >= 65:
            return "HIGH"
        if score >= 35:
            return "MEDIUM"
        return "LOW"
