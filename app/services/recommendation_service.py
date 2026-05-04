from __future__ import annotations

from rapidfuzz import fuzz

from app.data.repository import DataRepository
from app.models.recommendations import BusinessRecommendationRequest, BusinessRecommendationResponse, RecommendationRule
from app.utils.text import contains_any


class RecommendationService:
    def __init__(self, repository: DataRepository):
        self.repository = repository

    def get_rules(self) -> list[RecommendationRule]:
        return [RecommendationRule(**rule) for rule in self.repository.list_recommendation_rules()]

    def recommend(self, request: BusinessRecommendationRequest) -> BusinessRecommendationResponse:
        matched_rule = self._best_rule(request.business_type)
        departments: list[str] = []
        registrations: list[str] = []
        risk_flags: list[str] = []
        explanation: list[str] = []

        if matched_rule:
            departments.extend(matched_rule.primary_departments)
            registrations.extend(matched_rule.required_registrations)
            risk_flags.extend(matched_rule.risk_flags)
            explanation.append(f"Matched recommendation rule for business type '{matched_rule.business_type}'.")

        if request.handles_food:
            for value in ["FSSAI", "SHOP", "GST"]:
                if value not in registrations:
                    registrations.append(value)
            if "KSPCB" not in departments:
                departments.append("KSPCB")
            explanation.append("Food handling triggers food safety and environmental review.")

        if request.uses_machinery:
            for value in ["FACTORY", "LABOUR"]:
                if value not in departments:
                    departments.append(value)
            explanation.append("Machinery usage adds factory safety and labour compliance dependencies.")

        if request.employees and request.employees >= 10 and "LABOUR" not in departments:
            departments.append("LABOUR")
            risk_flags.append("Higher employee count may require additional labour filings")
            explanation.append("Employee count suggests labour registration and return filing checks.")

        if (request.pollution_category or "").lower() in {"orange", "red"}:
            if "KSPCB" not in departments:
                departments.append("KSPCB")
            risk_flags.append(f"Pollution category {request.pollution_category.lower()} needs consent validity tracking")
            explanation.append("Pollution category elevates KSPCB consent relevance.")

        if not departments:
            departments = ["SHOP", "GST"]
            registrations = ["Shop Establishment", "GST if threshold met"]
            explanation.append("No exact rule matched, so general business registration defaults were applied.")

        next_steps = [
            f"Prepare identity and address proofs for {request.district or 'the selected district'}.",
            "Check whether existing records already map to a UBID before creating a new one.",
            "Submit registrations department-wise and reconcile source record IDs into the UBID registry.",
        ]
        return BusinessRecommendationResponse(
            recommended_departments=sorted(dict.fromkeys(departments)),
            required_registrations=list(dict.fromkeys(registrations)),
            next_steps=next_steps,
            risk_flags=list(dict.fromkeys(risk_flags)),
            explanation=explanation,
        )

    def _best_rule(self, business_type: str) -> RecommendationRule | None:
        best: RecommendationRule | None = None
        best_score = 0
        for rule in self.get_rules():
            score = fuzz.WRatio(business_type.lower(), rule.business_type.lower())
            if score > best_score:
                best = rule
                best_score = score
        if best_score >= 75:
            return best
        if contains_any(business_type, ["food"]) and best:
            return best
        return None
