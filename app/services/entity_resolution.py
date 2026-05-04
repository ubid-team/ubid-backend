from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.data.repository import DataRepository
from app.models.business import BusinessRecord
from app.models.resolution import (
    CandidateMatch,
    MatchDecision,
    MatchExplanation,
    RecommendedAction,
    ResolveResponse,
)
from app.utils.scoring import exact_match_score, normalize_total, scaled_similarity
from app.utils.text import normalize_text


@dataclass(slots=True)
class ResolutionScores:
    name_score: int
    address_score: int
    pin_score: int
    phone_score: int
    pan_score: int
    gstin_score: int
    source_diversity_score: int

    @property
    def raw_total(self) -> int:
        return (
            self.name_score
            + self.address_score
            + self.pin_score
            + self.phone_score
            + self.pan_score
            + self.gstin_score
            + self.source_diversity_score
        )


class EntityResolutionService:
    MAX_INTERNAL_SCORE = 110

    def __init__(self, repository: DataRepository, settings: Settings):
        self.repository = repository
        self.settings = settings

    def resolve(self, record: BusinessRecord, limit: int = 10) -> ResolveResponse:
        self.repository.require_data()
        if self.repository.search_records.empty:
            return ResolveResponse(
                input_record=record,
                candidate_matches=[],
                recommended_action=RecommendedAction.create_new_ubid,
                needs_confirmation=False,
                confirmation_question=None,
            )

        record_name = normalize_text(record.business_name)
        record_address = normalize_text(record.address)
        candidate_matches: list[CandidateMatch] = []

        for _, row in self.repository.search_records.iterrows():
            scores = self._score_candidate(record, row.to_dict())
            final_score = normalize_total(scores.raw_total, self.MAX_INTERNAL_SCORE)
            if final_score < 25:
                continue
            decision = self._decision_for_score(final_score)
            explanation = self._build_explanation(record, row.to_dict(), scores)
            candidate_matches.append(
                CandidateMatch(
                    ubid=row.get("ubid") or None,
                    business_name=row.get("business_name") or row.get("business_name_raw") or "",
                    source_record_id=row.get("source_record_id", ""),
                    source=row.get("source_system", ""),
                    match_score=final_score,
                    decision=decision,
                    explanation=explanation,
                )
            )

        candidate_matches.sort(
            key=lambda candidate: (
                candidate.match_score,
                candidate.explanation.gstin_score + candidate.explanation.pan_score,
                candidate.explanation.name_score,
            ),
            reverse=True,
        )
        candidate_matches = candidate_matches[:limit]
        recommended_action, needs_confirmation, question = self._recommended_action(candidate_matches, record_name, record_address)
        return ResolveResponse(
            input_record=record,
            candidate_matches=candidate_matches,
            recommended_action=recommended_action,
            needs_confirmation=needs_confirmation,
            confirmation_question=question,
        )

    def _score_candidate(self, record: BusinessRecord, candidate: dict[str, str]) -> ResolutionScores:
        candidate_name = normalize_text(candidate.get("business_name"))
        candidate_address = normalize_text(candidate.get("address"))
        phone_score = exact_match_score(record.phone, candidate.get("phone"), 10)
        pan_score = exact_match_score(record.pan_hash, candidate.get("pan_hash"), 15)
        gstin_score = exact_match_score(record.gstin_hash, candidate.get("gstin_hash"), 15)
        return ResolutionScores(
            name_score=scaled_similarity(normalize_text(record.business_name), candidate_name, 30),
            address_score=scaled_similarity(normalize_text(record.address), candidate_address, 25),
            pin_score=exact_match_score(record.pin_code, candidate.get("pin_code"), 10),
            phone_score=phone_score,
            pan_score=pan_score,
            gstin_score=gstin_score,
            source_diversity_score=self.repository.source_diversity_score(candidate.get("ubid") or None),
        )

    def _decision_for_score(self, score: int) -> MatchDecision:
        if score >= self.settings.auto_link_threshold:
            return MatchDecision.auto_link
        if score >= self.settings.human_review_threshold:
            return MatchDecision.human_review
        return MatchDecision.no_match

    def _build_explanation(
        self,
        record: BusinessRecord,
        candidate: dict[str, str],
        scores: ResolutionScores,
    ) -> MatchExplanation:
        evidence: list[str] = []
        missing: list[str] = []
        if scores.name_score >= 22:
            evidence.append("Business names are highly similar")
        if scores.address_score >= 18:
            evidence.append("Address fields strongly align")
        if scores.pin_score:
            evidence.append("PIN code matched exactly")
        if scores.phone_score:
            evidence.append("Phone number matched exactly")
        if scores.pan_score:
            evidence.append("PAN hash matched exactly")
        if scores.gstin_score:
            evidence.append("GSTIN hash matched exactly")
        if scores.source_diversity_score >= 3:
            evidence.append("Multiple department links support the candidate UBID")
        if record.phone and not candidate.get("phone"):
            missing.append("No phone number available in candidate record")
        if record.pan_hash and not candidate.get("pan_hash"):
            missing.append("No PAN hash available in candidate record")
        if record.gstin_hash and not candidate.get("gstin_hash"):
            missing.append("No GSTIN hash available in candidate record")
        if record.address and not candidate.get("address"):
            missing.append("No address available in candidate record")
        return MatchExplanation(
            name_score=scores.name_score,
            address_score=scores.address_score,
            pin_score=scores.pin_score,
            phone_score=scores.phone_score,
            pan_score=scores.pan_score,
            gstin_score=scores.gstin_score,
            source_diversity_score=scores.source_diversity_score,
            evidence=evidence,
            missing_evidence=missing,
        )

    @staticmethod
    def _recommended_action(
        matches: list[CandidateMatch],
        record_name: str,
        record_address: str,
    ) -> tuple[RecommendedAction, bool, str | None]:
        if not matches:
            return (
                RecommendedAction.create_new_ubid,
                False,
                None,
            )
        top = matches[0]
        if top.decision == MatchDecision.auto_link and top.ubid:
            return (
                RecommendedAction.link_existing_ubid,
                True,
                f"High-confidence UBID match found for {top.business_name}. Link this record to {top.ubid}?",
            )
        if top.decision == MatchDecision.human_review:
            return (
                RecommendedAction.send_to_human_review,
                True,
                "Potential duplicate found. Send this record for human review before creating a new UBID?",
            )
        return (
            RecommendedAction.create_new_ubid,
            False,
            None,
        )
